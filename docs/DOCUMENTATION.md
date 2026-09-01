# Documentation du système — Assistant documentaire RAG du MINPMEESA

*Mémoire M2 MDSMS · ISSEA-CEMAC · Adnane MAMA IDISSA*

Ce document décrit **l'outillage technique** mobilisé pour construire le système
et **les fonctionnalités** offertes par l'application. Il complète le
[README](../readme.md) (prise en main) et
[ARCHITECTURE.md](ARCHITECTURE.md) (correspondance code ↔ chapitres du mémoire).

---

## 1. Présentation générale

Le système est un **assistant documentaire intelligent** fondé sur une
architecture **RAG hybride** (*Retrieval-Augmented Generation* — génération
augmentée par récupération). Il interroge en langage naturel le patrimoine
documentaire du MINPMEESA (Annuaire statistique, Notes de conjoncture, etc.) et
restitue des réponses **sourcées**, avec une garantie forte sur les **données
chiffrées** (reprises littéralement de la source, jamais recalculées).

Il répond à deux besoins :
1. **Produire l'Annuaire statistique** — réunir et vérifier les informations
   dispersées dans les documents sources (mode *production*, agents) ;
2. **Consulter les publications éditées** — accès rapide à une synthèse sourcée
   pour les décideurs (mode *consultation*).

---

## 2. Les outils et technologies utilisés

Le système est écrit en **Python 3** et n'utilise que des briques **libres,
exécutables localement** — un choix dicté par l'exigence de **souveraineté** des
données non publiées (plan A.6 du mémoire).

### 2.1 Traitement documentaire (ingestion)

| Outil | Rôle dans le système | Pourquoi ce choix |
|---|---|---|
| **PyMuPDF** (`pymupdf`) | Extraction du texte des PDF, **avec position des blocs** (pour lire les pages à deux colonnes dans l'ordre) | Rapide, précis, restitue l'ordre de lecture et conserve les nombres près de leurs libellés |
| Expressions régulières (`re`) | Nettoyage (césures, points de conduite), détection des sommaires et **formulaires d'annexe vides**, repérage des nombres | Léger, transparent, sans dépendance |

L'ingestion découpe chaque document en **passages** (≈180 mots, avec
recouvrement), en respectant les frontières de section et en gardant les
tableaux d'un seul tenant. Chaque passage reçoit ses **métadonnées** : document,
page, section, statut de diffusion (interne/publié), présence de chiffres, et un
**indice d'informativité** qui écarte les pages « creuses ».

### 2.2 Indexation et recherche

| Outil | Rôle | Pourquoi ce choix |
|---|---|---|
| **rank-bm25** | Index **lexical** BM25 (recherche par mots-clés exacts) | Référence de la recherche d'information ; excellent pour un terme précis (nom de tableau, région, indicateur) |
| **scikit-learn** (`TfidfVectorizer` + `TruncatedSVD`) | Index **vectoriel** de secours, 100 % hors-ligne (type LSA) | Fournit un signal sémantique sans aucun téléchargement de modèle ; garantit que tout tourne sans réseau |
| **sentence-transformers / fastembed** *(optionnel)* | Index **vectoriel** de référence : encodeur de phrases **multilingue** (français) | Vraie recherche sémantique (par le sens) ; exécuté localement (souveraineté) |
| **NumPy** | Calcul des similarités cosinus (produit matriciel) | Recherche vectorielle exacte et instantanée à cette échelle |

> **Deux canaux, une fusion.** La recherche lexicale (mots) et la recherche
> sémantique (sens) sont **complémentaires**. Le système les combine par
> **Reciprocal Rank Fusion (RRF)** — une méthode simple et robuste qui fusionne
> deux classements sans avoir à normaliser des scores d'échelles différentes.

### 2.3 Réordonnancement (reranking)

| Outil | Rôle | Pourquoi ce choix |
|---|---|---|
| **cross-encoder** (sentence-transformers) *(optionnel)* | Réévalue conjointement (question, passage) pour affiner le top des résultats | Plus précis que la première récupération sur les tout premiers rangs |
| Réordonnanceur « à traits » (interne) | Solution hors-ligne : couverture des termes, correspondance de phrase, concordance des nombres | Fonctionne sans modèle ; améliore la précision du sommet de liste |

### 2.4 Restitution et garde-fous

| Composant | Rôle |
|---|---|
| Synthèse **extractive** (par défaut) | Compose la réponse à partir de **phrases reprises verbatim** des sources → aucune hallucination possible |
| Restitution **par LLM local** *(optionnelle)* | Rédaction par un modèle de langage local (Ollama…), **sous contrainte** des garde-fous |
| **Garde-fou numérique** | Vérifie que chaque donnée chiffrée restituée figure **littéralement** dans une source ; retire toute valeur non sourcée |
| **Garde-fou de fidélité** | Mesure la part des énoncés effectivement soutenus par les passages |

### 2.5 Interface, évaluation, tests

| Outil | Rôle |
|---|---|
| **Streamlit** | Application web (les trois onglets, la charte MINPMEESA, la mise à jour de la documentation) |
| Module d'**évaluation** (interne) | Métriques nDCG@5, MRR, Precision@3, Recall@5 ; fidélité ; exactitude chiffrée ; test de cloisonnement ; validation des hypothèses |
| **pytest** | Tests automatiques (citation littérale, cloisonnement, fusion RRF, métriques) |

### 2.6 En résumé — la chaîne de traitement

```
PDF ─▶ Ingestion (PyMuPDF, nettoyage, découpage, métadonnées)
     ─▶ Indexation (BM25 + vecteurs)
     ─▶ Recherche hybride (filtre de mode ▸ fusion RRF ▸ reranking)
     ─▶ Restitution sourcée (synthèse + garde-fous numérique & fidélité)
     ─▶ Interface (Interroger · Collecte Annuaire · Mise à jour)
```

---

## 3. Les fonctionnalités de l'application

L'application web s'ouvre en un clic (`demarrer.bat`) et présente **trois
onglets**, plus une barre latérale de réglages.

### 3.1 Barre latérale — mode d'usage et réglages

- **Mode Production** (agents) : interroge **tout** le corpus (interne + publié).
- **Mode Consultation** (décideurs) : interroge **uniquement** les documents
  publiés. Le **cloisonnement** est garanti : un document interne non validé est
  totalement inaccessible en consultation.
- Affichage de l'état de l'index et de la couverture du dernier Annuaire.

### 3.2 Onglet « 🔎 Interroger »

- Question en langage naturel ; réponse composée de **passages sourcés**.
- Choix de l'étage de récupération (par défaut : **hybride + reranking**).
- **Filtres** par type de document et par année.
- **Contrôles qualité** affichés : exactitude chiffrée, fidélité, nombre de
  sources. Tout nombre non sourcé est signalé et retiré.
- **Passages sources** dépliables, avec leur statut (interne / publié).

### 3.3 Onglet « 📋 Collecte pour l'Annuaire »

C'est l'appui direct à la **production de l'Annuaire statistique**.

- Choix d'une **rubrique** de l'Annuaire (stock des PME, création, emploi,
  valeur ajoutée, trésorerie, conjoncture, inflation, appui aux PME).
- Le système réunit, pour la rubrique, les **constats sourcés** et surtout la
  colonne **« Données chiffrées »** ne conservant que les **statistiques
  exploitables** (pourcentages, effectifs), débarrassées des repères sans
  intérêt (numéros de liste, millésimes isolés).
- **Export CSV ou Markdown** pour préparer directement les tableaux et
  commentaires de l'Annuaire.

### 3.4 Onglet « ⚙️ Mettre à jour la documentation »

- **Liste** des documents du corpus (titre, type, statut, année).
- **Ajouter / remplacer** un document : téléversement d'un PDF + saisie des
  métadonnées (titre, type, statut de diffusion, année, trimestre).
- **Retirer** un document.
- **Reconstruire l'index** pour rendre les changements effectifs.
- **Images de l'application** : dépôt du **logo**, de la **bannière** et de la
  **couverture** de l'Annuaire.

### 3.5 Fonctionnalités transversales

- **Traçabilité** : chaque affirmation renvoie à sa source (document + page).
- **Citation littérale des chiffres** : garantie centrale du système.
- **Souveraineté** : fonctionne entièrement en local, sans envoi de données.
- **Deux populations d'utilisateurs** servies par le même index.

---

## 4. Utilisation en ligne de commande (rappel)

```bash
python -m rag_minpmeesa.app.cli build                     # construire l'index
python -m rag_minpmeesa.app.cli query "…" --mode production
python -m rag_minpmeesa.app.cli eval                      # évaluation (chapitre 4)
streamlit run rag_minpmeesa/app/streamlit_app.py          # interface web
```

---

## 5. Organisation des fichiers

```
rag_minpmeesa/
  config.py         paramètres, modes, seuils
  engine.py         moteur (point d'entrée)
  ingestion/        extraction, nettoyage, découpage, métadonnées
  index/            BM25 + vecteurs (backends enfichables)
  retrieval/        filtres, fusion RRF, reranking
  generation/       contexte, restitution, garde-fous (numérique, fidélité)
  evaluation/       métriques, jeu de test, protocole
  admin.py          gestion du corpus et des images (mise à jour)
  collecte.py       rubriques de collecte pour l'Annuaire
  app/              interface CLI + application web Streamlit
data/
  corpus/           PDF + registre de métadonnées
  gold/             jeu de test annoté
  results/          rapport d'évaluation
docs/               documentation (ce fichier, architecture, plan)
tests/              tests automatiques
```

---

## 6. Notes de reproductibilité

- Sans accès réseau aux modèles pré-entraînés, le système bascule
  automatiquement sur ses **substituts hors-ligne** (vectoriel TF-IDF/LSA et
  réordonnanceur à traits) : tout reste fonctionnel.
- La **configuration de référence** (encodeur multilingue + cross-encodeur,
  installés via `pip install fastembed`) améliore la recherche sémantique ;
  le protocole et les seuils d'évaluation restent identiques.
- Les hypothèses de **gain de temps** (H4/H5) relèvent d'un protocole terrain
  auprès des agents et décideurs (chapitre 2.6 du mémoire).
