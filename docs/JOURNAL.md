# Journal de bord du prototype (démarche §Règles de conduite)

Ce journal trace, étape par étape, les décisions de conception, les
paramètres retenus et les constats mesurés. Il est mis à jour à chaque
étape franchie. Toutes les valeurs proviennent d'exécutions réelles ;
aucune n'est inventée. Les artefacts d'évaluation (`outputs/runs/…`) sont
régénérables et volontairement non versionnés.

Régime d'exécution courant : **hors-ligne** — substitut TF-IDF + réduction
LSA (SVD tronquée). L'index résolu est `tfidf-lsa:384` (210 composantes
effectives, cf. constat §7.2). La configuration de référence
(transformeur multilingue + cross-encoder + LLM local) se branche par
`config.yaml` sur la machine de l'utilisateur, sans changement de code.

---

## Étape 1 — Assainissement du socle
- Externalisation intégrale des paramètres dans `config.yaml` ; plus aucune
  valeur expérimentale codée en dur (vérifié : surcharge `rrf_k` 60→77→60).
- Graines fixées en un point unique (`set_global_seed`) : `random`, NumPy,
  `PYTHONHASHSEED`.
- Dossiers de sortie horodatés (`outputs/runs`, `outputs/figures`).
- Tests d'ingestion ajoutés (segmentation, tableau d'un seul tenant,
  exclusion des formulaires vides, informativité, lecture de `config.yaml`).

## Étape 4 — Lexique métier + expansion de requête
- Dictionnaire `data/lexique/synonymes.yaml` (~60 familles métier).
- `QueryExpander` : déclenche une famille si un membre apparaît dans la
  requête normalisée, ajoute les autres membres (plafond configurable).
- Expansion **désactivable** (`use_expansion`) pour l'ablation §7.4.
- Canal lexical uniquement ; les canaux vectoriel et de restitution sont
  intacts.

## Étape 6 — Harnais d'évaluation C0–C5
- `run_evaluation()` : configurations C1 (lexical), C2 (vectoriel),
  C3 (hybride), C4 (hybride+rerank), C5 (C4+restitution), C0 (LLM, si
  disponible). Latence de récupération et de restitution chronométrées
  séparément.
- Sorties horodatées : `metrics_global.csv`, `runs_top10.csv`,
  `per_question.csv`, `restitution.csv`, `run_metadata.json` (versions de
  bibliothèques, pic RSS, régime, graine).
- Bornes des métriques respectées : dénominateur = nombre de passages
  pertinents **présents dans l'index** (la pertinence est annotée au niveau
  page, la récupération se fait au niveau passage) → P/R/nDCG ≤ 1.

## Étape 7 — Études d'ablation
Commande : `python -m rag_minpmeesa.app.cli ablations`. Cinq études, sorties
CSV dans `outputs/runs/ablations_<horodatage>/`.

- **7.1 — Constante de fusion k ∈ {1,5,10,20,60,100}.** Sur C4, nDCG@5
  culmine à k=10 (0,642) puis se tasse et se stabilise à k=60 (0,633).
  → Constat : sur des listes courtes, la valeur conventionnelle 60 écrase
  les écarts de rang ; k=10 est légèrement supérieur sur ce corpus. Le choix
  de 60 est conservé pour la comparabilité, mais documenté comme non optimal
  ici.
- **7.2 — Dimension de la réduction sémantique ∈ {64,128,256,384}.** Les
  dimensions 256 et 384 donnent toutes deux **210 composantes effectives**
  (rang de la matrice TF-IDF) avec des métriques identiques.
  → Constat : au-delà de 210, « conserver 210 composantes revient à une
  rotation de l'espace TF-IDF et non à une réduction ». Les dimensions plus
  basses (64, 128) réduisent effectivement et changent les scores.
- **7.3 — Taille de segment / recouvrement ∈ {(120,30),(180,40),(260,60)}.**
  Segments courts (120) → meilleure P@3 (0,537) mais moindre rappel ;
  segments longs (260) → meilleur R@5 (0,722) et nDCG@5 (0,682). Le réglage
  courant (180,40) est un compromis.
- **7.4 — Expansion activée / désactivée.** L'expansion **dégrade** les
  métriques sur le canal lexical (nDCG@5 0,613→0,374) et l'hybride sur ce
  jeu de test dérivé du corpus (lexicalement biaisé, comme relevé par
  l'encadreur). → Constat : l'expansion est à réévaluer sur le jeu de test
  terrain (§8) rédigé indépendamment du corpus ; désactivable par défaut.
- **7.5 — Réordonnancement par catégorie (CU1–CU5).** Le reranking aide
  partout ou reste neutre ; gains nets sur CU4 (nDCG@3 0,352→0,617) et CU5
  (0,412→0,592), neutre sur CU2.

## Étape 5 — Garde-fous de restitution
Quatre propriétés non négociables (démarche §0) vérifiées ou renforcées.

- **Citation littérale des nombres.** Le garde-fou numérique
  (`generation/numeric.py`) reprend chaque donnée chiffrée verbatim d'une
  source ; toute valeur non retrouvée est retirée (test
  `test_answer_numeric_guardrail` : exactitude = 1).
- **Cloisonnement au niveau requête, sur tout le corpus.** Nouveau test
  `test_cloisonnement_couvre_tout_le_corpus` : sur l'intégralité de l'index,
  le filtre du mode consultation n'autorise **aucun** passage interne (garantie
  indépendante de la requête, appliquée avant tout scoring — jamais un filtre
  d'affichage).
- **Abstention calibrée par courbe** (`evaluation/calibration.py`, commande
  CLI `calibration`). 36 requêtes (18 en périmètre issues du jeu de test,
  18 hors périmètre rédigées indépendamment du corpus,
  `data/gold/hors_perimetre.json`). Constat décisif : le score de fusion
  **normalisé** ne discrimine pas (toujours ≈ 1 en tête, J de Youden ≈ 0,17),
  mais le **score lexical BM25 brut** sépare parfaitement les deux populations
  (en périmètre ≥ 15,05 ; hors périmètre ≤ 9,79 ; J = 1,0, zéro fuite, zéro
  réponse perdue). Le signal d'abstention retenu est donc le meilleur BM25 ;
  seuil calibré à 12,0 (centré dans l'intervalle de séparation ; recommandé
  9,91). Tests `test_abstention_hors_perimetre` / `..._repond_en_perimetre`.
- **Ancrage phrase par phrase.** Chaque énoncé de la synthèse est rattaché à
  son passage source (`SourcedSentence`) et classé soutenu / non soutenu par le
  rapport de fidélité (`guardrails.py`).

## Étape 9 — Statistiques et figures
Commandes : `python -m rag_minpmeesa.app.cli stats` et `… figures`.

- **Tests appariés (`evaluation/stats.py`).** Wilcoxon signé sur les nDCG@5
  par question + décompte gains/pertes/égalités + Kendall τ, pour toutes les
  paires C1–C4. Constats (régime hors-ligne, n=18) :
  - C1 (lexical) significativement le plus faible (p ≈ 0,0015 contre chaque
    autre configuration) ;
  - **C4 > C3** : le réordonnancement apporte un gain significatif
    (Δ nDCG@5 = +0,056 ; p = 0,018 ; 7 gains / 0 perte / 11 égalités ;
    τ = 0,81) — sens de l'hypothèse H2 ;
  - C2 (vectoriel) vs C3 (hybride) : différence **non significative**
    (p = 0,42 ; Δ = 0,047), et C2 vs C4 sous le seuil de granularité — à
    rapporter honnêtement : dans le régime hors-ligne TF-IDF, l'hybridation
    n'améliore pas nettement le vectoriel seul.
- **Note de granularité.** Avec n=18 et une pertinence annotée à la page
  (≈3 passages pertinents/question), la résolution d'une moyenne est
  ≈ 1/(3n) ≈ 0,0185 ; les écarts inférieurs (ex. C2 vs C4) ne sont pas
  interprétés.
- **Ventilation par catégorie** CU1–CU5 (`stats_par_categorie.csv`).
- **Figures 300 dpi** (`evaluation/figures.py`, `outputs/figures/`) :
  balayage de k (C3/C4) et calibration de l'abstention (distributions des
  confiances + sensibilité/spécificité selon le seuil).

---

## À faire (étapes restantes)
- **Étape 3/10** — Protocoles Encoder/Reranker + bascule automatique,
  `docs/INSTALLATION.md`, `docs/DEMONSTRATION.md` (scénario 5 requêtes).
- **Côté terrain (machine de l'utilisateur)** — corpus ≥ 1000 passages + RAP,
  transfert des caches de modèles + Ollama, jeu de test ≥ 50 questions
  doublement annotées (kappa), C0/C5 avec LLM, mesure du gain opérationnel.
