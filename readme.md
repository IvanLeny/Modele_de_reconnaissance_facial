# Système RAG hybride pour le patrimoine documentaire du MINPMEESA

> **Mémoire de Master 2** — *Conception et évaluation d'un système intelligent
> fondé sur une architecture RAG hybride pour l'exploitation du patrimoine
> documentaire du MINPMEESA, en appui à la production de l'Annuaire statistique
> et du Rapport annuel de performance.*
>
> Adnane MAMA IDISSA — M2 Data Science et Modélisation Statistique (MDSMS), ISSEA-CEMAC.

Ce dépôt contient l'**artefact logiciel** du mémoire : un système de génération
augmentée par récupération (RAG) *hybride*, *traçable* et *souverain*, conçu pour
interroger en langage naturel les documents du ministère et restituer des
réponses **sourcées**, avec une garantie forte sur les **données chiffrées**.

---

## 1. Ce que fait le système

- **Ingère** l'Annuaire statistique et les Notes de conjoncture (PDF) : extraction
  sensible aux colonnes, nettoyage, segmentation, métadonnées.
- **Indexe** le corpus deux fois : recherche **lexicale** (BM25) et recherche
  **sémantique** (vecteurs denses).
- **Récupère** par une chaîne **hybride** : filtrage → fusion des classements
  (RRF) → réordonnancement (reranking).
- **Restitue** une synthèse **ancrée dans les sources**, où **toute donnée
  chiffrée est reprise littéralement** du passage d'origine et accompagnée de sa
  référence (garde-fou contre l'hallucination numérique).
- Fonctionne selon **deux modes** : *production* (agents, corpus interne + publié)
  et *consultation* (décideurs, corpus publié uniquement), avec **cloisonnement**
  strict des documents internes.

## 2. Structure du dépôt

```
rag_minpmeesa/            # le paquet Python (artefact)
  config.py               # 3.1  configuration, modes, seuils a priori
  engine.py               # 3.1  moteur de haut niveau (point d'entrée)
  schema.py               # 3.2  modèle de données (Document, Chunk, Result)
  ingestion/              # 3.2  extraction → nettoyage → segmentation → métadonnées
  index/                  # 3.3  BM25 + vecteurs (backends enfichables)
  retrieval/              # 3.4  filtres + fusion RRF + reranking
  generation/             # 3.5–3.6  contexte, restitution, garde-fous numériques
  evaluation/             # 4    métriques, jeu de test, protocole complet
  app/                    # 3.7  interfaces CLI et web (Streamlit)
data/
  corpus/                 # les PDF + registry.json (métadonnées + statut)
  gold/                   # jeu de test annoté (chapitre 4.1)
  results/                # rapport d'évaluation (JSON + Markdown)
docs/                     # ARCHITECTURE.md + plan du mémoire
tests/                    # tests unitaires et d'intégration
```

Une **carte détaillée code ↔ mémoire** figure dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 3. Installation

```bash
pip install -r requirements.txt
```

Le socle est **100 % exécutable hors-ligne** (aucun modèle à télécharger).
Pour la **configuration de référence** (déploiement local souverain avec un
encodeur de phrases multilingue et un cross-encodeur), installer en plus :

```bash
pip install fastembed            # ou : sentence-transformers
```

Le système détecte automatiquement le meilleur backend disponible et bascule sur
le substitut hors-ligne (TF-IDF/LSA + réordonnanceur à traits) si aucun modèle
pré-entraîné n'est accessible.

## 4. Utilisation

### Ligne de commande

```bash
# 1) Construire l'index à partir du corpus
python -m rag_minpmeesa.app.cli build

# 2) Interroger — mode production (agents)
python -m rag_minpmeesa.app.cli query \
  "Quelle est la répartition du stock des PME par région en 2023 ?" --mode production

# 3) Interroger — mode consultation (décideurs)
python -m rag_minpmeesa.app.cli query \
  "Quel a été le taux de croissance du Cameroun au 2e trimestre 2024 ?" --mode consultation

# 4) Lancer l'évaluation complète (chapitre 4)
python -m rag_minpmeesa.app.cli eval
```

### Interface web

```bash
streamlit run rag_minpmeesa/app/streamlit_app.py
```

Sélecteur de mode, filtres par métadonnées, synthèse sourcée, passages dépliables
et tableau de bord des contrôles qualité (exactitude chiffrée, fidélité).

### En Python

```python
from rag_minpmeesa.engine import RAGEngine
from rag_minpmeesa.config import Mode

eng = RAGEngine().ensure_ready()
ans = eng.query("trésorerie des PME au 2e trimestre 2024", mode=Mode.PRODUCTION)
print(ans.summary)                     # synthèse sourcée
print(ans.numeric_audit.to_dict())     # audit des données chiffrées
print(ans.sources)                     # références citées
```

### Restitution par un LLM local (optionnelle)

Pour activer la rédaction par un modèle de langage **local** (p. ex. Ollama), sous
la contrainte des garde-fous numériques :

```bash
export RAG_LLM_BASE_URL="http://localhost:11434/v1"
export RAG_LLM_MODEL="llama3"
# puis, dans config.py : GenerationConfig.synthesis = "llm"
```

## 5. Résultats d'évaluation

Le protocole (chapitre 4) produit une **étude d'ablation** de la récupération,
l'évaluation de la **restitution ancrée**, le **test de cloisonnement** et la
**validation des hypothèses** au regard des seuils fixés *a priori* (Tableau A.3).
Le rapport complet est régénéré dans [`data/results/evaluation.md`](data/results/evaluation.md).

Faits saillants (jeu de test de 18 questions annotées) :

- **Restitution ancrée** : fidélité **1,00**, **exactitude chiffrée 1,00**
  (100 % des nombres restitués sont sourcés) → **H3 validée**.
- **Cloisonnement** : **0 % de fuite** de documents internes en mode consultation.
- **Récupération** : la chaîne hybride se classe au niveau des meilleures
  configurations simples sur nDCG@5 et MRR ; le reranking améliore la précision
  du sommet de liste (Precision@3).

> **Note de reproductibilité.** Cet environnement n'a pas accès aux modèles
> pré-entraînés : les chiffres du dépôt sont obtenus avec les **substituts
> hors-ligne**. La configuration de référence (encodeur multilingue +
> cross-encodeur) est attendue au-dessus de ces valeurs sur la complémentarité
> hybride (H1) et l'apport du reranking (H2). Le protocole et les seuils sont
> identiques ; seuls les modèles changent. Les hypothèses H4/H5 (gain de temps)
> relèvent d'un protocole terrain auprès des agents et décideurs.

## 6. Tests

```bash
pytest -q
```

Les tests vérifient les propriétés de conception : citation littérale des nombres,
cloisonnement des modes, correction de la fusion RRF et des métriques.

## 7. Corpus

| Document | Type | Statut | Année |
|---|---|---|---|
| Annuaire statistique 2022 sur les PMEESA | annuaire | publié | 2022 |
| Note de conjoncture — 2e trimestre 2024 | conjoncture | publié | 2024 |
| Note de conjoncture — 3e trimestre 2024 | conjoncture | publié | 2024 |
| Note de conjoncture — 1er trimestre 2025 | conjoncture | *interne* | 2025 |

Le statut de diffusion (`data/corpus/registry.json`) est une décision de
déploiement du ministère ; la note T1-2025 est marquée *interne* pour **démontrer
et évaluer** le cloisonnement des deux modes.

---

*Projet académique — ISSEA-CEMAC. Les données proviennent des publications du
MINPMEESA (Division des Études, des Projets et de la Prospective).*
