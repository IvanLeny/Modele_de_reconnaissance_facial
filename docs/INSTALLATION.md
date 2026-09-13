# Installation et exécution (démarche §3, §10)

Système RAG hybride du MINPMEESA. Cible : **100 % local**, Ubuntu 24.04,
Python 3.11, aucun GPU requis. Deux régimes possibles :

- **hors-ligne** (défaut, aucun téléchargement) : substitut TF-IDF/LSA +
  réordonnanceur à traits. Toute la chaîne s'exécute et s'évalue sans réseau.
- **référence** (déploiement souverain recommandé) : encodeur transformeur
  multilingue + cross-encodeur + LLM local (Ollama), tous exécutés sur la
  machine. Aucune donnée ne sort du réseau.

Le système **sélectionne automatiquement le meilleur backend disponible** et
bascule sur le substitut hors-ligne si aucun modèle n'est accessible
(`backend: auto`). Passer de l'un à l'autre ne demande aucune modification du
code — seulement `config.yaml` et la présence (ou non) des modèles.

---

## 1. Prérequis

```bash
python3 --version        # 3.11 attendu
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` installe le socle hors-ligne (PyMuPDF, rank-bm25,
scikit-learn, numpy, scipy, pyyaml, streamlit, matplotlib). Aucun modèle n'est
téléchargé à cette étape.

## 2. Construire l'index et interroger

```bash
python -m rag_minpmeesa.app.cli build                      # construit l'index
python -m rag_minpmeesa.app.cli query "répartition du stock des PME par région"
python -m rag_minpmeesa.app.cli query "croissance CEMAC 2025" --mode consultation
python -m rag_minpmeesa.app.cli info                       # état de l'index
```

Interface web (3 onglets : interrogation, collecte annuaire, mise à jour
documentaire) :

```bash
streamlit run rag_minpmeesa/app/streamlit_app.py
```

## 3. Évaluation, ablations, statistiques, figures

```bash
python -m rag_minpmeesa.app.cli harness       # harnais C0-C5 + latence + 4 CSV (§6)
python -m rag_minpmeesa.app.cli ablations      # k, dim SVD, segments, expansion, rerank (§7)
python -m rag_minpmeesa.app.cli calibration    # seuil d'abstention (§5)
python -m rag_minpmeesa.app.cli stats          # Wilcoxon, win/lose/tie, Kendall (§9)
python -m rag_minpmeesa.app.cli figures        # figures 300 dpi (§9)
pytest -q                                       # 20 tests, sans réseau
```

Les sorties horodatées sont écrites dans `outputs/runs/` et `outputs/figures/`.

---

## 4. Passer en configuration de référence (modèles locaux)

### 4.0 Voie rapide : script clé en main + vérification

Sur une machine **autorisée** (accès réseau), un seul script installe et met en
cache les trois modèles de référence (encodeur, cross-encodeur, LLM Ollama) :

```bash
bash scripts/setup_modeles.sh          # RAG_SETUP_LLM=qwen2.5:7b pour un autre LLM
```

À tout moment, un diagnostic indique ce qui est prêt et ce qui manque (ne
télécharge rien) :

```bash
python -m rag_minpmeesa.app.cli doctor
```

Il renvoie un code de sortie 0 si l'encodeur de référence est disponible, 1
sinon (le système bascule alors sur le substitut hors-ligne). Les sections
4.1–4.2 détaillent la procédure manuelle sous-jacente.

### 4.1 Encodeur et réordonnanceur (transformeurs)

Sur une machine sans accès au dépôt de modèles, **transférer le cache** depuis
un poste connecté (aucune donnée du corpus n'y transite, seulement les poids
publics des modèles).

Modèles de référence (déjà déclarés dans `config.yaml`) :

- encodeur : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ;
- réordonnanceur : `cross-encoder/ms-marco-MiniLM-L-6-v2`.

Procédure (poste connecté → clé USB → machine cible) :

```bash
# Sur le poste connecté : pré-télécharger dans un cache local
export HF_HOME=/chemin/vers/cache_hf
python -c "from fastembed import TextEmbedding; \
           TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
python -c "from sentence_transformers import CrossEncoder; \
           CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Copier le dossier cache_hf sur la machine cible, puis y définir :
export HF_HOME=/chemin/vers/cache_hf
export HF_HUB_OFFLINE=1        # interdit tout accès réseau : 100 % local
```

Forcer le régime souhaité (facultatif — `auto` suffit si le cache est présent) :

```yaml
# config.yaml
embedding:
  backend: "transformer"      # au lieu de "auto"
```

ou par variable d'environnement, utile pour rejouer une expérience hors-ligne :

```bash
export RAG_EMBEDDING_BACKEND=tfidf     # force le substitut hors-ligne
```

Après changement de backend, **reconstruire l'index** (`… cli build`).

### 4.2 Rédaction par LLM local (Ollama)

Le mode extractif (défaut) est le plus défendable : la synthèse est composée de
phrases déjà présentes dans les sources, sans aucun risque d'hallucination. Le
mode LLM produit une rédaction plus fluide, sous les mêmes garde-fous numériques.

```bash
# Installer Ollama puis récupérer un modèle 7-8B (poste connecté ou miroir interne)
ollama pull llama3.1:8b
ollama serve                    # expose http://localhost:11434
```

```yaml
# config.yaml
restitution:
  synthesis: "llm"
  llm_base_url: "http://localhost:11434/v1"   # point d'accès compatible OpenAI
  llm_model: "llama3.1:8b"
```

Si le point d'accès LLM est indisponible, le système **bascule automatiquement**
sur la restitution extractive (aucune interruption de service).

---

## 5. Reproductibilité

- Toute l'aléa est fixée par `seed: 42` dans `config.yaml` (démarche §1).
- Aucun paramètre expérimental n'est codé en dur : modifier `config.yaml`
  suffit à rejouer une variante.
- Chaque exécution d'évaluation écrit un `run_metadata.json` (versions des
  bibliothèques, backend effectif, pic mémoire, graine).
- Journal des décisions et constats : `docs/JOURNAL.md`.
