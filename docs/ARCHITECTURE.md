# Architecture du dispositif — assistant de rédaction des commentaires MINPMEESA

Ce document décrit l'architecture **réelle** du système (`src/`) et la met en
correspondance avec le schéma d'intention initial.

## 1. Nature du système

Ce n'est **pas** un chatbot question→réponse. C'est un **assistant de rédaction
sous contraintes** : l'entrée est un couple **(indicateur, exercice)**, la sortie
est un **commentaire** (ou une **note de perspective**) accompagné de ses sources.
Ce choix découle directement des quatre garanties non négociables du cahier des
charges : il est bien plus sûr de contraindre la génération autour d'un indicateur
identifié que de répondre à une question libre.

## 2. Chaîne de traitement

```
┌──────────────────────────────────────────────────────────────────┐
│  ENTRÉE : (indicateur, exercice)                                   │
│  — depuis l'interface (sélection) ou la CLI                        │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  ASSEMBLAGE DU CONTEXTE            src/retrieval/context.py         │
│  Recherche « hybride » réelle :                                    │
│   · Metadata  → filtre TEMPOREL  (WHERE exercice < N) + par type   │
│   · Lexical   → recouvrement de tokens + similarité d'intitulé     │
│                 (homologues antérieurs du même indicateur)         │
│   · Valeurs   → tableaux de l'Annuaire de l'exercice N             │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  APPARIEMENT                      src/pairing/                      │
│  Code indicateur STABLE d'une édition à l'autre :                  │
│  graphique du Rapport ↔ tableau de l'Annuaire ↔ commentaire        │
│  (rôle structurant proche d'un « mini-graphe » de connaissances)   │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  GÉNÉRATION                       src/generation/                  │
│   · RÉFÉRENCE : LLM (Ollama local, ou cloud OpenAI-compatible)     │
│   · DÉGRADÉ   : composition extractive déterministe (repli)        │
│  Prompt en 5 blocs ; température 0,2 ; graine fixe.                │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  GARDE-FOUS (post-génération)     src/guards/                      │
│   · numeric.py   → citation littérale, valeurs non sourcées écartées│
│   · provenance.py→ référence attachée à chaque énoncé              │
│   · abstention.py→ abstention explicite si sources insuffisantes   │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  SORTIE : commentaire + sources + régime (référence/dégradé)       │
│  Validation humaine avant export (interface).                      │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Correspondance avec le schéma d'intention initial

| Bloc du schéma initial | Réalisation dans `src/` |
|---|---|
| Question utilisateur | **Adapté** : sélection (indicateur, exercice), pas de question libre — exigence de sûreté du cahier des charges. |
| Analyse de la question | `assembler_contexte()` — préparation de l'intitulé et des filtres. |
| Recherche hybride (BM25 + Vector + Metadata) | **Metadata** : présent (filtre temporel + type). **Lexical** : recouvrement de tokens + similarité d'intitulé. **Vector** : non activé dans `src/` (déterminisme privilégié ; embeddings offline possibles en extension). |
| Knowledge Graph | **Approché** par la table d'appariement (identité de l'indicateur entre éditions). Pas de graphe traversable à part entière. |
| Données statistiques | Tableaux des Annuaires (`src/ingestion/tables.py`). |
| RAG | Génération augmentée par le contexte récupéré et filtré. |
| LLM | Ollama local / cloud OpenAI-compatible / repli extractif. |
| Réponse + sources + contexte | **Renforcé** par les garde-fous (littéralité, provenance, abstention). |

### Écarts assumés et justifiés
- **Pas de question libre** : la génération est contrainte autour d'un indicateur
  identifié → garanties de fidélité tenables.
- **Vectoriel non activé** : le déterminisme du mode dégradé sert de borne de
  fidélité (C4) et de solution de repli hors-ligne intégrale.
- **Graphe de connaissances léger** : l'appariement suffit à relier valeurs et
  commentaires d'un même indicateur dans le temps, sans la lourdeur d'un graphe.

Ces écarts peuvent être comblés en **extension** (recherche vectorielle offline,
graphe explicite) sans remettre en cause les garanties, si le jury le demande.

## 4. La note d'analyse de perspective

`src/generation/perspective.py` produit une **synthèse transversale** de tout le
corpus (chiffres-clés, signaux de conjoncture, éléments de contexte), structurée
en sections, sous les **mêmes garde-fous** (chiffres littéraux, sources,
abstention). Objectif : **aider la décision** du responsable, pas commenter un
seul tableau.

## 5. Régimes et reproductibilité

| Régime | Génération | Stockage | Usage |
|---|---|---|---|
| Dégradé | Extractif déterministe | SQLite en mémoire | Développement, tests, borne de fidélité C4, hors-ligne intégral |
| Référence | LLM (Ollama local / cloud) | PostgreSQL | Déploiement ; chiffres C0-C1 définitifs |

Le régime est **inscrit dans chaque sortie**. Paramètres de génération fixes
(température 0,2, graine) pour la reproductibilité.
