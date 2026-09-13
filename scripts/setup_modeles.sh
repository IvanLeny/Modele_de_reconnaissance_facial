#!/usr/bin/env bash
# =====================================================================
#  Installation clé en main de la CONFIGURATION DE RÉFÉRENCE (démarche §3)
#  À lancer SUR UNE MACHINE AUTORISÉE (accès réseau), une seule fois.
#
#    bash scripts/setup_modeles.sh
#
#  Le script :
#    1. installe les bibliothèques de modèles (fastembed, sentence-transformers) ;
#    2. pré-télécharge les caches des modèles de référence (encodeur + rerank) ;
#    3. installe Ollama si absent et récupère le LLM local ;
#    4. rappelle les étapes suivantes (config.yaml + doctor + build).
#
#  Aucune donnée du corpus MINPMEESA ne transite : seuls les poids publics des
#  modèles sont téléchargés. Pour un poste HORS LIGNE, exécuter ce script sur un
#  poste connecté puis recopier le dossier de cache (voir docs/INSTALLATION.md §4).
# =====================================================================
set -euo pipefail

# --- Paramètres (alignés sur config.yaml) ----------------------------------- #
ENCODER="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANKER="cross-encoder/ms-marco-MiniLM-L-6-v2"
LLM="${RAG_SETUP_LLM:-llama3.1:8b}"     # surchargez : RAG_SETUP_LLM=qwen2.5:7b bash …
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

bold() { printf "\n\033[1m%s\033[0m\n" "$1"; }

bold "1/4 — Installation des bibliothèques de modèles"
python3 -m pip install --upgrade "fastembed>=0.3" "sentence-transformers>=2.2"

bold "2/4 — Pré-téléchargement des caches de modèles (HF_HOME=$HF_HOME)"
python3 - "$ENCODER" "$RERANKER" <<'PY'
import sys
enc, rer = sys.argv[1], sys.argv[2]
print(f"  · encodeur   : {enc}")
try:
    from fastembed import TextEmbedding
    m = TextEmbedding(enc)
    v = next(iter(m.embed(["amorçage du cache"])))
    print(f"    OK (fastembed, dim={len(v)})")
except Exception as e:
    print(f"    fastembed a échoué ({type(e).__name__}); essai sentence-transformers…")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(enc)
    print("    OK (sentence-transformers)")
print(f"  · rerank     : {rer}")
from sentence_transformers import CrossEncoder
CrossEncoder(rer)
print("    OK (CrossEncoder)")
PY

bold "3/4 — LLM local (Ollama)"
if ! command -v ollama >/dev/null 2>&1; then
  echo "  Ollama absent — installation…"
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "  Ollama déjà installé : $(ollama --version 2>/dev/null || echo présent)"
fi
# Démarre le serveur en arrière-plan s'il ne tourne pas déjà.
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "  Démarrage du serveur Ollama en arrière-plan…"
  (ollama serve >/tmp/ollama.log 2>&1 &) || true
  sleep 3
fi
echo "  Récupération du modèle : $LLM"
ollama pull "$LLM"

bold "4/4 — Étapes suivantes (à faire à la main)"
cat <<EOF
  a) Dans config.yaml :
       embedding:
         backend: "transformer"
       restitution:
         synthesis: "llm"
         llm_base_url: "http://localhost:11434/v1"
         llm_model: "$LLM"

  b) Reconstruire l'index avec l'encodeur de référence :
       python3 -m rag_minpmeesa.app.cli build

  c) Vérifier que tout est prêt :
       python3 -m rag_minpmeesa.app.cli doctor

  Pour un poste HORS LIGNE : recopiez "$HF_HOME" sur la machine cible et
  définissez-y HF_HOME + HF_HUB_OFFLINE=1 (voir docs/INSTALLATION.md §4).
EOF
bold "Terminé."
