# Architecture du système et correspondance avec le mémoire

Ce document relie chaque composant logiciel aux sections du mémoire, afin que le
jury puisse retrouver dans le code la réalisation de chaque choix de conception.

## Vue d'ensemble

```
                          ┌──────────────────────────────────────────┐
   Corpus (PDF)           │              INGESTION (3.2)              │
   Annuaire + Notes  ───▶ │  extract → clean → chunk → métadonnées    │
   de conjoncture         │  (statut de diffusion : interne / publié) │
                          └───────────────────┬──────────────────────┘
                                              ▼
                          ┌──────────────────────────────────────────┐
                          │              INDEXATION (3.3)             │
                          │   BM25 (lexical)   +   vecteurs (dense)   │
                          └───────────────────┬──────────────────────┘
   Requête + Mode ──▶  ┌───────────────────────────────────────────────┐
   (production/         │            RÉCUPÉRATION HYBRIDE (3.4)          │
    consultation)       │  filtre (cloisonnement + métadonnées)         │
                        │  → BM25 ▏ dense → fusion RRF → reranking       │
                        └───────────────────┬───────────────────────────┘
                                            ▼
                        ┌───────────────────────────────────────────────┐
                        │          RESTITUTION CONTRÔLÉE (3.5–3.6)        │
                        │  contexte sourcé → synthèse ancrée             │
                        │  garde-fou numérique (citation littérale)      │
                        │  garde-fou de fidélité                         │
                        └───────────────────┬───────────────────────────┘
                                            ▼
                          Réponse sourcée + audit qualité (CLI / Web, 3.7)
```

## Correspondance fichier ↔ section du mémoire

| Section du mémoire | Composant | Fichier(s) |
|---|---|---|
| 3.1 Architecture générale et environnement | Configuration, moteur | `config.py`, `engine.py` |
| 3.2 Ingestion (extraction, nettoyage, segmentation, métadonnées) | Ingestion | `ingestion/registry.py`, `ingestion/extract.py`, `ingestion/clean.py`, `ingestion/chunk.py`, `ingestion/pipeline.py` |
| 3.3 Indexation lexicale et vectorielle | Index | `index/lexical.py`, `index/vector.py`, `index/embeddings.py`, `index/text_utils.py`, `index/store.py` |
| 3.4 Recherche hybride : fusion et reranking | Récupération | `retrieval/filters.py`, `retrieval/fusion.py`, `retrieval/rerank.py`, `retrieval/pipeline.py` |
| 3.5 Construction du contexte et restitution ancrée | Génération | `generation/context.py`, `generation/answer.py` |
| 3.6 Citation littérale et garde-fous | Garde-fous | `generation/numeric.py`, `generation/guardrails.py` |
| 3.7 Prototype, deux modes et interface | Interfaces | `app/cli.py`, `app/streamlit_app.py` |
| 4.1–4.6 Expérimentation, évaluation, hypothèses | Évaluation | `evaluation/metrics.py`, `evaluation/gold.py`, `evaluation/run_eval.py`, `data/gold/gold_testset.json` |

## Les deux modes d'usage (plan A.1, A.2)

Le mode est porté par la métadonnée **statut de diffusion** de chaque document :

- **Mode production (amont)** — agents ; corpus `interne` + `publié` ; requêtes
  pointues ; besoin : localiser, vérifier, rapprocher.
- **Mode consultation (aval)** — décideurs ; corpus `publié` uniquement ;
  requêtes larges ; besoin : synthèse rapide.

Le cloisonnement est appliqué **avant** tout scoring (`retrieval/filters.py`,
`MODE_VISIBILITY`) : un utilisateur en consultation ne peut jamais atteindre un
document interne non validé. Le test correspondant (`tests/test_system.py`) et la
mesure du taux de fuite (`evaluation/run_eval.py`, §4.4) le vérifient.

## La règle de restitution contrôlée (choix de conception central, A.2)

> Toute donnée chiffrée restituée doit être reprise **littéralement** d'un passage
> source (sans reformulation, recalcul ni arrondi) et accompagnée de sa référence.

Réalisation :
- `generation/numeric.py` extrait et **apparie** chaque nombre restitué à une
  source ; tout nombre non retrouvé est signalé et retiré.
- En restitution **extractive** (défaut souverain), les phrases sont reprises
  verbatim : l'hallucination numérique est structurellement impossible.
- En restitution **LLM** (optionnelle, modèle local), la consigne impose la
  citation littérale et les garde-fous filtrent la sortie a posteriori.

## Choix d'implémentation notables

- **Fusion RRF** (`retrieval/fusion.py`) : combine des classements d'échelles
  différentes (BM25 vs cosinus) sans normalisation ni paramètre appris.
- **Backends enfichables** (`index/embeddings.py`, `retrieval/rerank.py`) :
  configuration de référence = encodeur multilingue + cross-encodeur exécutés
  **localement** (souveraineté, plan A.6) ; substituts hors-ligne (TF-IDF/LSA et
  réordonnanceur à traits) pour garantir l'exécution sans accès réseau.
- **Reranking à deux étages** : le classement final mélange le score de reranking
  et le prior de fusion (`config.rerank_blend`), pour ne pas dégrader le rappel.
- **Extraction sensible aux colonnes** (`ingestion/extract.py`) : les notes de
  conjoncture à deux colonnes sont lues colonne par colonne, préservant la prose.

## Points d'extension documentés

- Extraction tabulaire fine (PyMuPDF-layout, Camelot) pour les grands tableaux.
- Index vectoriel approché (FAISS/HNSW) pour un passage à l'échelle.
- Baseline génératif « sans récupération » (mode LLM local) pour compléter la
  mesure de H3 (réduction du taux d'énoncés non soutenus).
- Protocole terrain de mesure du temps (H4/H5) auprès des agents et décideurs.
