"""
Diagnostic de la configuration de référence (démarche §3).

Vérifie, SUR LA MACHINE CIBLE, la disponibilité des trois modèles de référence
(encodeur transformeur, cross-encodeur, LLM local) et indique précisément ce
qu'il faut installer. N'effectue aucun téléchargement ; se contente de tenter
un chargement local et de rapporter l'état.

À lancer après le transfert des caches de modèles et le démarrage d'Ollama
(voir docs/INSTALLATION.md §4) :

    python -m rag_minpmeesa.app.cli doctor
"""
from __future__ import annotations

import os
from typing import Tuple

from ..config import get_settings

OK = "✅ OK"
KO = "❌ ABSENT"
WARN = "⚠️  PARTIEL"


def check_encoder(model_name: str) -> Tuple[str, str]:
    """Tente de charger l'encodeur transformeur (fastembed puis sentence-transformers)."""
    # 1) fastembed (ONNX, léger)
    try:
        from fastembed import TextEmbedding
        m = TextEmbedding(model_name)
        v = next(iter(m.embed(["test de disponibilité"])))
        return OK, f"fastembed, dim={len(v)}"
    except Exception as e:
        fe = f"fastembed indisponible ({type(e).__name__})"
    # 2) sentence-transformers (PyTorch)
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(model_name)
        return OK, f"sentence-transformers, dim={m.get_sentence_embedding_dimension()}"
    except Exception as e:
        return KO, f"{fe} ; sentence-transformers indisponible ({type(e).__name__})"


def check_reranker(model_name: str) -> Tuple[str, str]:
    try:
        from sentence_transformers import CrossEncoder
        ce = CrossEncoder(model_name)
        _ = ce.predict([("requête", "passage")])
        return OK, "sentence-transformers CrossEncoder"
    except Exception as e:
        return KO, f"CrossEncoder indisponible ({type(e).__name__})"


def check_llm(base_url: str, model: str) -> Tuple[str, str]:
    base = os.environ.get("RAG_LLM_BASE_URL") or base_url
    mdl = os.environ.get("RAG_LLM_MODEL") or model
    if not base:
        return WARN, "aucun point d'accès LLM configuré (mode extractif utilisé)"
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        names = [m.get("id", "") for m in data.get("data", [])]
        present = (mdl in names) if mdl else True
        detail = f"{base} joignable ; modèles: {', '.join(names) or '—'}"
        if mdl and not present:
            return WARN, detail + f" ; « {mdl} » absent (faire : ollama pull {mdl})"
        return OK, detail
    except Exception as e:
        return KO, f"{base} injoignable ({type(e).__name__}) — lancer « ollama serve »"


def run_doctor() -> int:
    s = get_settings()
    print("=" * 70)
    print(" DIAGNOSTIC DE LA CONFIGURATION DE RÉFÉRENCE (démarche §3)")
    print("=" * 70)
    print(f" Backend d'embedding configuré : {s.embedding.backend}")
    print(f" Mode de restitution            : {s.generation.synthesis}")
    print("-" * 70)

    rows = []
    st, det = check_encoder(s.embedding.transformer_model)
    rows.append(("Encodeur transformeur", s.embedding.transformer_model, st, det))
    st, det = check_reranker(s.retrieval.reranker_model)
    rows.append(("Cross-encodeur (rerank)", s.retrieval.reranker_model, st, det))
    st, det = check_llm(s.generation.llm_base_url, s.generation.llm_model)
    rows.append(("LLM local (Ollama)", s.generation.llm_model or "—", st, det))

    for nom, modele, statut, detail in rows:
        print(f" {statut}  {nom}")
        print(f"        modèle : {modele}")
        print(f"        détail : {detail}")
    print("-" * 70)

    enc_ok = rows[0][2] == OK
    if enc_ok:
        print(" → Configuration de référence disponible pour l'encodage.")
        print("   Mettez `embedding.backend: transformer` dans config.yaml,")
        print("   puis reconstruisez l'index : python -m rag_minpmeesa.app.cli build")
    else:
        print(" → Encodeur de référence indisponible : le système fonctionnera en")
        print("   régime SUBSTITUT TF-IDF/LSA (100 % hors-ligne, aucun téléchargement).")
        print("   Pour activer la référence, voir docs/INSTALLATION.md §4 ou lancer")
        print("   le script scripts/setup_modeles.sh sur une machine autorisée.")
    print("=" * 70)
    # Code de sortie : 0 si l'encodeur de référence est prêt, 1 sinon (utile en CI).
    return 0 if enc_ok else 1
