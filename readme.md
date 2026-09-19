# Assistant de rédaction des commentaires statistiques — MINPMEESA

> **Mémoire de Master 2** — *Conception et évaluation d'un dispositif d'aide à la
> rédaction des commentaires analytiques accompagnant les publications
> statistiques du MINPMEESA, sous garanties de fidélité et de traçabilité.*
>
> Adnane MAMA IDISSA — M2 Data Science et Modélisation Statistique (MDSMS), ISSEA-CEMAC.

Ce dépôt contient l'**artefact logiciel** du mémoire. Le système **assiste la
rédaction** des commentaires qui accompagnent les tableaux de l'Annuaire
statistique, et produit une **note d'analyse de perspective** transversale pour
l'aide à la décision — le tout **100 % local**, **traçable** et **sans jamais se
tromper sur un chiffre**.

---

## ⚠️ Un seul système fait foi : `src/`

Le dépôt contient encore un **ancien** paquet `rag_minpmeesa/` (un chatbot
question→réponse, première version abandonnée). **Ne t'y réfère plus.** Le
système du mémoire est **`src/`**, décrit ci-dessous. L'ancien sera retiré (voir
[§ Nettoyage](#nettoyage)).

---

## 1. Ce que fait le système

Le système ne répond **pas** à des questions libres : il **rédige des
commentaires** sous garanties. Deux productions :

### a) Commentaire d'un indicateur
Pour un **indicateur** et un **exercice** donnés, il reçoit :
- les **valeurs** du tableau de cet indicateur (Annuaire de l'exercice) ;
- les **commentaires des éditions antérieures** du même indicateur ;

et produit un **paragraphe de commentaire** en registre institutionnel.

### b) Note d'analyse de perspective (aide à la décision)
À partir de **tout le corpus** (annuaires, rapports, notes de conjoncture,
documents de contexte), il produit une **note transversale** structurée destinée
à **éclairer la décision** du responsable — sous les mêmes garde-fous.

## 2. Les quatre garanties non négociables

1. **Jamais faux sur un nombre.** Tout chiffre est cité **littéralement** depuis
   sa source ; une valeur non retrouvée dans les données est **écartée**.
2. **Le patron vient du passé, les valeurs du présent.** On réutilise la *forme*
   des commentaires antérieurs, **jamais leurs valeurs**.
3. **Aucune information postérieure** à l'exercice traité (filtre temporel
   `WHERE exercice < N` au niveau de la requête).
4. **Chaque énoncé porte sa référence** ; en l'absence de sources suffisantes, le
   système **s'abstient** explicitement.

Ces garanties sont **indépendantes du modèle** : elles s'appliquent *après*
génération (`src/guards/`), que le texte vienne d'un LLM ou du repli extractif.

## 3. Architecture réelle

```
(indicateur, exercice)                      ← entrée : pas une question libre
        │
        ▼
 Assemblage du contexte  ── filtre temporel (exercice < N) + filtre par type
        │                    · valeurs de l'exercice (tableaux Annuaire)
        │                    · commentaires antérieurs du même indicateur
        │                      (code exact + similarité d'intitulé)
        ▼
 Table d'appariement  ── code indicateur stable d'une édition à l'autre
        │                (graphique du rapport ↔ tableau de l'annuaire)
        ▼
      Génération  ── LLM local (Ollama) OU cloud OpenAI-compatible
        │            OU repli extractif déterministe (mode dégradé)
        ▼
     Garde-fous  ── citation littérale · provenance · abstention
        ▼
 Commentaire + sources + régime          ← sortie tracée et validable
```

> Détail complet et correspondance avec ton schéma initial :
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 4. Démarrage rapide (mode dégradé, immédiat, hors-ligne)

Aucun modèle requis : la chaîne s'exécute et s'évalue entièrement en local.

```bash
pip install -r requirements.txt

python -m src.app.cli demo                 # démonstration en 5 temps
python -m src.app.cli generer --exercice 2023 --n 0
python -m src.app.cli perspective --exercice 2023   # note de perspective
python -m src.eval.runner                  # harnais d'évaluation (CSV)
python -m src.eval.stats                   # statistiques + figures 300 dpi
streamlit run src/app/main.py              # interface (4 espaces)
pytest tests/test_src_*.py -q              # tests
```

## 5. Régime de référence (rédaction par un LLM)

Le code parle le protocole **OpenAI** (`/chat/completions`). Trois variables
d'environnement suffisent — **aucune ligne de code à changer**.

### Option A — Ollama **local** (déploiement souverain, recommandé pour le mémoire)
```bash
ollama pull llama3.1:8b
set RAG_LLM_BASE_URL=http://localhost:11434/v1
set RAG_LLM_MODEL=llama3.1:8b
```

### Option B — Cloud OpenAI-compatible (**dépannage** de développement)
Utile si le téléchargement local échoue. ⚠️ Contredit la souveraineté : à réserver
au banc d'essai, en le signalant dans le mémoire.
```bash
set RAG_LLM_BASE_URL=https://api.groq.com/openai/v1
set RAG_LLM_MODEL=llama-3.1-8b-instant
set RAG_LLM_API_KEY=gsk_votre_cle
```

Le **régime** effectif est inscrit dans chaque sortie
(`référence (llm:…)` vs `dégradé (extractif)`).

## 6. Base persistante PostgreSQL (machine cible)

```bash
set RAG_PG_DSN=host=localhost dbname=minpmeesa user=postgres password=VOTRE_MDP
python -m src.ingestion.ingest_postgres        # ingère les 18 documents
python -m src.ingestion.add_document "chemin\vers\nouveau.pdf"   # enrichir la base
```

La base est **mise à jour depuis l'interface** (onglet Ingestion) ou en CLI.

## 7. Structure du dépôt (`src/`)

```
src/
  ingestion/     extraction PDF · tableaux · métadonnées · appariement · ingestion
  pairing/       table d'appariement (code indicateur stable entre éditions)
  retrieval/     store SQLite / PostgreSQL · assemblage du contexte (filtre temporel)
  generation/    prompt · génération (LLM/extractif) · note de perspective
  guards/        garde-fous : numérique · provenance · abstention
  eval/          harnais C0-C4 + baseline · métriques · statistiques + figures
  app/           interfaces CLI et web (Streamlit)
data/corpus/     18 PDF (annuaires, rapports, notes de conjoncture, contexte)
db/schema_pg.sql schéma PostgreSQL (sans pgvector, portable)
docs/            ARCHITECTURE.md · INSTALLATION.md · DEMONSTRATION.md · JOURNAL.md
tests/           tests unitaires (test_src_*.py)
```

## 8. Ordre conseillé pour la soutenance

1. `python -m src.app.cli demo` — montre les garanties (contrôle, abstention).
2. `streamlit run src/app/main.py` — génération d'un commentaire, validation humaine.
3. `python -m src.app.cli perspective --exercice 2024` — note d'aide à la décision.
4. `python -m src.eval.runner` puis `python -m src.eval.stats` — chiffres + figures.

## Nettoyage

Le paquet `rag_minpmeesa/`, les anciens tests (`test_system.py`,
`test_ingestion.py`) et les docs dupliquées (`*_NOUVEAU*.md`) sont **obsolètes**
(leur contenu à jour est désormais dans les fichiers canoniques). Ils peuvent
être retirés sans risque (l'historique git les conserve) :

```bash
git rm -r rag_minpmeesa tests/test_system.py tests/test_ingestion.py
git rm docs/INSTALLATION_NOUVEAU.md docs/DEMONSTRATION_NOUVEAU.md docs/JOURNAL_NOUVEAU_PROTOTYPE.md
```

---

*Projet académique — ISSEA-CEMAC. Données issues des publications du MINPMEESA
(Division des Études, des Projets et de la Prospective).*
