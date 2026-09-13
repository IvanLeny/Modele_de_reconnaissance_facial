# Scénario de démonstration (démarche §10)

Cinq requêtes exécutées sur le prototype illustrent les propriétés non
négociables du système (démarche §0). **Tous les extraits ci-dessous sont des
sorties réelles du moteur**, reproductibles par :

```bash
python -m rag_minpmeesa.app.cli query "…" --mode production   # ou --mode consultation
```

Régime d'exécution : hors-ligne (index `tfidf-lsa`, réordonnanceur à traits).
La configuration de référence (transformeur + cross-encodeur + LLM local)
produit les mêmes garde-fous, avec une rédaction plus fluide.

---

## 1. Réponse sourcée — chaque énoncé porte sa référence

**Requête (production)** : « Quelle est la répartition du stock des PME par
région ? »

> • *DONNÉES STATISTIQUES SUR LES PME — Tableau 4 : Répartition du stock des PME
> estimé en 2023 selon la Région…*
> **[Annuaire statistique 2022 sur les PMEESA, p. 16]**

- Exactitude chiffrée : **1.00** (232 / 232 nombres sourcés)
- Fidélité : **1.00** (tous les énoncés soutenus par le contexte)

Le passage tabulaire est retrouvé d'un seul tenant, en-tête et valeurs
solidaires ; la référence (document + page) accompagne l'énoncé.

---

## 2. Donnée chiffrée reprise littéralement

**Requête (production)** : « Quelle proportion de PME déclarait une trésorerie
difficile au 2ᵉ trimestre 2024 ? »

> • *Par contre l'année dernière à la même période, 52,2 % de PME déclaraient
> une trésorerie difficile…*
> **[Note de conjoncture - 2e trimestre 2024, p. 10-11]**

- Exactitude chiffrée : **1.00** (25 / 25)

Le pourcentage `52,2 %` est repris **verbatim** de la source : aucun recalcul,
aucun arrondi. C'est la première propriété non négociable — le système ne peut
pas se tromper sur un nombre.

---

## 3. Abstention sur une requête hors périmètre

**Requête (production)** : « Qui a remporté la dernière Coupe d'Afrique des
Nations ? »

> ⚠ **Aucune source suffisamment pertinente n'a été trouvée dans le corpus
> autorisé pour ce mode (confiance lexicale 8.74 < seuil 12.00). Le système
> s'abstient de répondre plutôt que de produire une synthèse mal étayée.**

Le sujet est absent du corpus MINPMEESA. La confiance lexicale (meilleur BM25 =
8,74) tombe sous le seuil calibré (12,0, cf. `docs/JOURNAL.md` §5). Le système
**sait ne pas répondre** — troisième propriété non négociable.

---

## 4. Cloisonnement des modes

**Requête** : « mesures d'appui à 200 entreprises, 1er trimestre 2025 »

- **Mode production** : les documents internes de travail (notes non validées)
  sont accessibles et peuvent être restitués.
- **Mode consultation** (décideurs) : la même requête ne renvoie **que** des
  passages publiés ; aucun passage interne n'apparaît.

Le cloisonnement est appliqué au **filtrage de la base**, avant tout scoring
(cf. `rag_minpmeesa/retrieval/filters.py`), et vérifié sur l'intégralité du
corpus par le test `test_cloisonnement_couvre_tout_le_corpus`. Ce n'est jamais
un simple filtre d'affichage — deuxième propriété non négociable.

---

## 5. Garde-fou numérique : rejet d'une valeur non sourcée

Ce garde-fou protège le **mode LLM** (rédaction par un modèle local). Sur un
brouillon qui introduirait un nombre absent des sources :

> Brouillon : « Le stock des PME atteint 393 954 entreprises, soit une hausse de
> **12,5 %** sur un an. »
> Sources : « Le stock des PME est estimé à 393 954 entreprises en 2023. »

Audit numérique réel :

```
exactitude 0.50  (1 / 2 nombres sourcés)
valeurs rejetées : ['12,5']
```

`393 954` est validé (présent dans la source) ; `12,5 %`, absent, est **signalé
et retiré**. En mode extractif (défaut souverain), ce cas ne peut pas survenir :
la synthèse est composée de phrases déjà présentes dans les sources.

---

## Synthèse des propriétés démontrées

| # | Propriété non négociable (démarche §0)                | Démonstration |
|---|-------------------------------------------------------|---------------|
| 1 | Ne peut pas se tromper sur un nombre                  | §2, §5        |
| 2 | Ne peut pas divulguer une donnée non publiée         | §4            |
| 3 | Sait s'abstenir                                       | §3            |
| 4 | Tout est tracé et sourcé                              | §1, §2        |
