# Résultats de l'évaluation — système RAG hybride MINPMEESA

- Jeu de test : **18 questions** annotées.
- Encodeur vectoriel : `tfidf-lsa:384`
- Réordonnanceur : `feature-reranker`
- Index : {'n_chunks': 211, 'embedding_backend': 'tfidf-lsa:384', 'embedding_dim': 210, 'n_documents': 4}

> **Configuration hors-ligne (substituts).** Cet environnement d'exécution n'a pas d'accès réseau aux modèles pré-entraînés : les résultats ci-dessous sont produits avec le substitut vectoriel TF-IDF/LSA et/ou le réordonnanceur à traits. La **configuration de référence** — encodeur de phrases multilingue et cross-encodeur exécutés localement — est attendue au-dessus de ces valeurs, notamment sur la complémentarité hybride (H1) et l'apport du reranking (H2). Le protocole et les seuils restent identiques ; seuls les modèles changent.

## 4.2 Récupération (étude d'ablation)

| Configuration | nDCG@5 | MRR | Precision@3 | Recall@5 |
|---|---|---|---|---|
| lexical | 0.613 | 0.861 | 0.463 | 0.605 |
| vectoriel | 0.624 | 0.821 | 0.481 | 0.634 |
| hybride | 0.622 | 0.858 | 0.463 | 0.619 |
| hybride+rerank | 0.618 | 0.800 | 0.500 | 0.623 |

## 4.3 Restitution ancrée dans les sources

- Fidélité moyenne (énoncés soutenus) : **1.000**
- Exactitude chiffrée moyenne (nombres sourcés) : **1.000**
- Taux de citation correcte du document de référence : **1.000**
- Rappel des données chiffrées de référence : **0.696**
- Refus (aucune source pertinente) : 0

## 4.4 Cloisonnement des modes (sécurité)

- Questions à information interne : 4
- Taux de fuite en mode consultation : **0.000** (attendu : 0)
- Taux d'accès en mode production : **1.000**

## 4.6 Validation des hypothèses (seuils a priori, Tableau A.3)

- **H1** (fusion hybride) : gain nDCG@5 = -0.002, gain MRR = -0.003 → ❌ non validée
- **H2** (reranking) : gain nDCG@5 = -0.004, gain P@3 = +0.037 → ❌ non validée
- **H3** (ancrage) : fidélité = 1.000, exactitude chiffrée = 1.000 → ✅ validée
- **Cloisonnement** : fuite = 0.000 → ✅ validée
- **H4/H5** (gain de temps) : ⏳ protocole terrain — Hypothèses de gain de temps : protocole contrôlé auprès d'agents et de décideurs (chap. 2.6). Non exécutable dans l'environnement logiciel ; critères fixés a priori au Tableau A.3.

> H3 — La réduction du taux d'énoncés non soutenus vs 'sans récupération' requiert un baseline génératif (mode LLM local) ; les critères de fidélité et d'exactitude chiffrée de l'ancrage sont validés ici.