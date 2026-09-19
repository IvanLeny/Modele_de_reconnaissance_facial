# Journal de bord — nouveau prototype (assistant de rédaction des commentaires)

Journal tenu au fil de l'eau (cahier des charges §6.3), destiné à la section
3.6.4 du mémoire. Chaque difficulté est consignée avec sa résolution. Toutes les
valeurs proviennent d'exécutions réelles.

---

## Corpus effectivement disponible (au 2026-09-16)

16 des 19 documents. **Deux couples appariés complets : 2022 et 2023.**

| Type | Présents | Manquants |
| --- | --- | --- |
| Annuaires | 2022, 2023 | 2021, 2024 |
| Rapports d'analyse | 2021, 2022, 2023, 2024 | — |
| Notes de conjoncture | T3 2022, T4 2023, T1/T2/T3 2024, T1 2025 | T4 2024 |
| Contexte | 2 bulletins, 2 notes de perspective | — |

---

## Étape 1 — Socle et ingestion

### Difficulté majeure : identifier l'exercice malgré des repères trompeurs
Le cahier des charges (§2) prévient de trois pièges, tous rencontrés :
1. **Nom de fichier trompeur** — l'Annuaire 2022 est livré sous le nom
   `stat2023fr.pdf`.
2. **Titre courant erroné** — le fichier livré comme « annuaire_statistique_2022 »
   est en réalité l'Annuaire de l'exercice **2023** (édition juin 2024) ; son
   en-tête de page reprend à tort « ANNUAIRE STATISTIQUE 2022 ».
3. **Plans variables** — l'ordre des chapitres change d'une édition à l'autre :
   aucun appariement ne peut se fonder sur la position.

**Résolution.** L'exercice est déterminé sur le **contenu** et non sur la page de
titre seule (dont l'en-tête est justement pollué par le titre courant erroné) :
année récente **dominante dans le corps** du document, renforcée par les mentions
explicites « exercice 20XX » (`src/ingestion/metadata.py:detect_exercice`).
Vérifié exact sur les 16 documents (test `tests/test_src_ingestion.py`), y
compris les deux cas pièges ci-dessus.

### Difficulté : distinguer les types de documents
Le mot « conjoncture » figure aussi dans les rapports et annuaires, et les notes
de perspective comportent des graphiques comme les rapports d'analyse. Une simple
recherche de mot-clé se trompe.

**Résolution.** Classement par **structure** et **titre**, dans cet ordre :
note de conjoncture (titre/­trimestre, sans catalogue) → contexte (titre
« bulletin d'information » / « note de perspective ») → annuaire (« annuaire
statistique » + ≥ 10 tableaux) → rapport d'analyse (≥ 5 graphiques commentés).
Les identités ont d'abord été établies par comptage (2023 : 19 graphiques,
2024 : 15 — concordance exacte avec le cahier des charges), ce qui a permis de
donner aux fichiers des noms canoniques fiables. Tous les types sont corrects
(même test).

### Extraction
`src/ingestion/extract.py` : extraction PDF avec position des blocs, détection
des lignes récurrentes (titres courants, numéros de page) par récurrence sur
≥ 50 % des pages, et ordre de lecture tenant compte des mises en page à deux
colonnes.

### Valeurs à reporter au mémoire (§8)
- Nombre de pages et de tableaux/graphiques par document : relevé
  automatiquement (ex. Annuaire 2023 : 86 p., 63 tableaux ; Rapport 2023 :
  33 p., 19 graphiques ; Rapport 2024 : 42 p., 15 graphiques).
- Taille de passage / recouvrement : à fixer dans `config.yaml` à l'étape de
  segmentation.

## Étape 2 — Traitement des tableaux

`src/ingestion/tables.py` linéarise chaque tableau en **énoncés élémentaires**
« ligne | colonne = valeur », en conservant la correspondance valeur ↔ en-têtes.

- **En-têtes multi-niveaux** (exercice + unité) reconstitués par remplissage
  horizontal des cellules fusionnées puis composition du chemin de colonne :
  la valeur `342` devient « Primaire | 2016 · Effectif = 342 ».
- **Millésimes** (« 2016 », « 2023 (e) ») traités comme en-têtes temporels, pas
  comme des valeurs (`_is_data_value`).
- Extraction fondée sur `page.find_tables` de PyMuPDF.

**Valeurs mesurées (matière pour le mémoire §2.3.1 / §8) :**

| Annuaire | Tableaux exploitables | Valeurs linéarisées |
| --- | --- | --- |
| 2021 | 60 | 1 443 |
| 2022 | 36 | 556 |
| 2023 | 83 | 2 161 |
| 2024 | 92 | 2 368 |

**Limite connue, à documenter :** le chemin de colonne peut comporter un jeton
d'en-tête redondant lorsque la ligne d'unités est lacunaire (ex. « Effectif · % »).
La correspondance valeur ↔ (ligne, exercice, unité) reste correcte ; seul
l'affichage du chemin est parfois verbeux. Tests : `tests/test_src_tables.py`.

## Étape 7 — Garde-fous (cœur de la contribution)

Les garde-fous opèrent APRÈS la génération, sur le texte produit, indépendamment
du modèle (règle d'architecture centrale du cahier des charges).

- **Citation littérale** (`src/guards/numeric.py`), 4 règles : normalisation des
  séparateurs/marques décimales ; exclusion des millésimes ; interdiction du
  recalcul (comparaison littérale, aucune valeur dérivée) ; **portée = bloc de
  données de l'exercice, jamais les commentaires antérieurs**. Une valeur non
  appariée entraîne le retrait de la proposition + signalement.
- **Traçabilité** (`src/guards/provenance.py`), 2 niveaux : proposition chiffrée
  → tableau de l'Annuaire ; proposition d'interprétation → commentaire antérieur
  dont la formulation est reprise (rapprochement par similarité de tokens).
- **Abstention** (`src/guards/abstention.py`), 2 déclencheurs : absence de
  tableau/valeurs (univoque) ; faiblesse du contexte de référence (score de
  confiance à seuil **calibré** à l'étape 9, jamais choisi).

Vérifié sur exemples contrôlés (`tests/test_src_guards.py`, 10 tests), dont les
deux cas décisifs du cahier des charges :
- une **valeur inventée** (5,9 %) voit sa proposition retirée ;
- une **valeur d'un commentaire antérieur** (393 166 PME) absente du bloc de
  données de l'exercice voit aussi sa proposition retirée (motif : révision des
  estimations — l'Annuaire contemporain indique 393 175).

## Étape 3 — Table d'appariement

`src/pairing/build.py` extrait les intitulés des **graphiques** des rapports et
des **tableaux** des annuaires, puis propose des appariements candidats par
similarité de libellé (Jaccard de tokens), avec un **code indicateur stable**
d'une édition à l'autre (année et unités neutralisées). `src/pairing/schema.py`
fournit le contrôle de cohérence (chaque code dans ≥ 2 éditions) et le **kappa de
Cohen** pour la double saisie.

Le cahier des charges impose une validation **manuelle** avec double saisie : ce
module prépare le fichier de travail (`data/pairing/appariement_<exercice>.csv`,
colonne `statut` = candidat / à_vérifier), il ne tranche pas.

**Résultats (candidats, score ≥ 0,30) :**

| Exercice | Graphiques | Appariements candidats |
| --- | --- | --- |
| 2021 | 9 | 8 |
| 2022 | 15 | 13 |
| 2023 | 19 | 15 |
| 2024 | 15 | 14 |

Exemples corrects à score élevé : G1→T4 (répartition par région, 0,67),
G4→T7 (PME créées dans les CFCE, 0,83). Les cas ambigus (ex. OES) sont marqués
« à_vérifier » pour arbitrage humain. Tests : `tests/test_src_pairing.py`.

### Valeurs à reporter au mémoire (§8)
- Nombre de graphiques commentés par rapport : 2021 : 9 ; 2022 : 15 ; 2023 : 19 ;
  2024 : 15.
- Taux d'accord de la double saisie (kappa) : à calculer après la double
  annotation manuelle (fonction `cohen_kappa` prête).

## Étapes 4a / 5 / 6 — Stockage, récupération, génération

### Stockage (Étape 4a)
`db/schema.sql` définit le schéma PostgreSQL + pgvector (documents, passages,
tableaux, appariement) pour la machine cible. `src/retrieval/store.py` en fournit
une réalisation **SQLite** (même schéma logique) pour le développement et les
tests hors-ligne. On bascule par `config.yaml` sans changer le code.

### Récupération du contexte (Étape 5)
- **Filtrage temporel strict** dans la clause WHERE (`commentaires_anterieurs` :
  `WHERE code=? AND exercice < N`). Test dédié : aucun passage d'exercice ≥ N ne
  remonte, vérifié pour tous les N (`tests/test_src_retrieval.py`).
- **Assemblage du contexte en trois blocs étiquetés** (`retrieval/context.py`) :
  valeurs de l'exercice N (seules citables), valeurs antérieures (contexte),
  commentaires antérieurs (patron de forme). Le `bloc_donnees()` est le seul
  contexte transmis au garde-fou numérique.

### Génération contrainte (Étape 6)
- **Instruction en 5 blocs** (`generation/prompt.py`), règles de restitution
  **répétées après les exemples** (biais d'attention positionnelle).
- **Sortie structurée** en propositions élémentaires (`generation/structured.py`).
- **Client enfichable** (`generation/generate.py`) : régime RÉFÉRENCE via Ollama
  (compatible OpenAI, température 0,2, 700 jetons, graine) ; régime DÉGRADÉ par
  composition extractive déterministe. Le régime actif est renvoyé dans le
  résultat et sera inscrit dans `run_metadata.json`.
- Vérifié de bout en bout en mode dégradé : la chaîne produit un commentaire
  **100 % ancré** (exactitude 1,0), la forme d'un commentaire antérieur est
  reprise **sans aucune de ses valeurs** (`tests/test_src_generation.py`).

**41 tests au total pour le nouveau prototype.**

## Étapes 8-9 — Harnais d'évaluation et statistiques

`src/ingestion/ingest.py` peuple le dépôt depuis le vrai corpus (valeurs des
annuaires ; commentaires des rapports segmentés par graphique, hors sommaire) et
fournit le commentaire publié de référence par (exercice, indicateur).
`src/eval/metrics.py` (ROUGE-1/2/L, similarité, ancrage, couverture, toutes
bornées ≤ 1), `src/eval/runner.py` (C0–C4 + baseline naïve, 5 sorties CSV +
textes produits + run_metadata) et `src/eval/stats.py` (Wilcoxon apparié,
win/lose/tie, granularité 1/n, figures 300 dpi).

**Résultats mesurés (régime dégradé, 57 unités évaluables) :**

| Comparaison (ROUGE-1) | Δ moyen | gagne/perd/égal | p (Wilcoxon) |
| --- | --- | --- | --- |
| C1 vs C0 (apport de l'ancrage) | **+0,163** | 34 / 0 / 23 | ≈ 0 |
| C2 vs C1 (filtrage) | 0 | 0 / 0 / 57 | — |
| C3 vs C2 (garde-fous + abstention) | −0,144 | 0 / 34 / 23 | ≈ 0 |

- **C1 ≫ C0** : ajouter les commentaires homologues antérieurs améliore
  significativement la qualité rédactionnelle (résultat net, 34 gains / 0 perte).
- **C3 < C2 en ROUGE mais exactitude ↑ (0,935 → 0,957) et abstention 40 %** :
  c'est le compromis fidélité/couverture au cœur de H2 — le système complet
  préfère écarter ou s'abstenir plutôt que produire un énoncé mal étayé.
- Granularité 1/n = 0,0175 : les écarts inférieurs ne sont pas interprétés.
- Figures : `figure_generation_configs.png`, `figure_generation_exactitude_couverture.png`.

**Limites honnêtes du régime dégradé (à lever sur la machine cible) :**
- sans LLM, C0/C1/C2/C4 partagent le générateur extractif : leurs écarts fins
  ne se révèlent pleinement qu'en régime de référence (Ollama) ;
- l'appariement automatique (codes dérivés des intitulés) n'aligne les
  homologues consécutifs que pour une minorité d'indicateurs ; la **table
  d'appariement validée à la main** (Étape 3) fournira les codes stables qui
  renforceront C1/C3 et la baseline.

## Étape 10 — Interface, démonstration et documentation

- `src/app/main.py` : interface Streamlit à **trois espaces** (ingestion,
  génération, export validé), sans aucune fonctionnalité superflue. Les trois
  affichages qui portent les garanties sont présents : référence par proposition,
  signalement d'une proposition écartée, message d'abstention. Aucun commentaire
  n'est exporté sans validation humaine (case « Valider » par proposition).
- `src/app/cli.py` : même chaîne hors interface — commande `demo` (scénario en
  5 temps) et `generer`.
- `docs/DEMONSTRATION_NOUVEAU.md` : scénario en 5 temps avec **sorties réelles**
  (dont valeur antérieure écartée et valeur inventée écartée).
- `docs/INSTALLATION_NOUVEAU.md` : exécution en mode dégradé, puis bascule en
  régime de référence (Ollama + PostgreSQL/pgvector) par `config.yaml`.

À ce stade, **les dix étapes du cahier des charges sont couvertes**, avec 66
tests verts. Ce qui reste strictement dépendant de la machine cible : les
chiffres finaux C0/C1 sous LLM, l'empreinte mémoire du modèle (§8), et la
validation manuelle de la table d'appariement (double saisie + kappa).

## Étape 4a (suite) — PostgreSQL sur la machine cible

- `db/schema_pg.sql` : schéma PostgreSQL **sans pgvector** (applicable tel quel
  sous Windows, où pgvector n'est pas installé par défaut). La récupération étant
  structurée (code indicateur, intitulé, filtrage temporel SQL), la colonne
  vectorielle n'est pas nécessaire ; pgvector reste une extension future
  (`db/schema.sql`).
- `src/retrieval/pg_store.py` : dépôt PostgreSQL (psycopg2), **même interface**
  que le dépôt SQLite ; filtrage temporel dans la clause WHERE.
- `src/ingestion/ingest_postgres.py` : crée le schéma, ingère le corpus dans
  PostgreSQL, vérifie que le filtrage temporel exclut tout exercice ≥ N, et
  affiche les compteurs (persistance vérifiable après réouverture).
- L'ingestion est factorisée (`ingest.populate`) : le MÊME code peuple SQLite ou
  PostgreSQL. La bascule se fait par la variable RAG_PG_DSN / `config.yaml`.
- Environnement cible relevé : **PostgreSQL 18** (§3.1.5).

## Maintenance — ajout de documents à la base (§3.1.5)

La base est **enrichissable à l'avenir**, directement depuis le prototype :
- `src/ingestion/ingest.py:ingest_document` ingère UN document quelconque en
  détectant son type et son exercice (annuaire → valeurs ; rapport →
  commentaires appariés ; note/contexte → paragraphes de vocabulaire) ;
- `src/ingestion/populate_all` peuple la base avec **les 18 documents** (les 6
  notes de conjoncture et les 4 documents de contexte sont désormais inclus,
  soit 426 passages de vocabulaire en plus) ;
- commande de maintenance : `python -m src.ingestion.add_document "<pdf>"`
  ajoute un nouveau PDF à la base PostgreSQL sans tout réingérer ;
- l'espace **« Ingestion »** de l'interface Streamlit permet de **déposer un PDF**
  qui entre dans la base (persistant si RAG_PG_DSN est défini).

L'évaluation reste fondée sur les seuls couples appariés (`populate`), donc les
chiffres du chapitre 4 sont inchangés ; l'enrichissement documentaire sert le
vocabulaire et l'usage opérationnel.
