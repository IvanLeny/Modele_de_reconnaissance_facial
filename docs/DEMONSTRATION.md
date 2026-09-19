# Scénario de démonstration — assistant de rédaction des commentaires (Étape 10)

Cinq temps, **sorties réelles du prototype** (reproductibles). Les temps 3 et 4
sont ceux qui rendent visible la garantie centrale du travail.

Commande : `python -m src.app.cli demo` (ou l'interface : `streamlit run src/app/main.py`).

Régime ci-dessous : **dégradé (extractif)**, faute de LLM dans l'environnement de
construction. Sur la machine cible, Ollama produit une prose fluide ; **les
garde-fous, eux, sont identiques dans les deux régimes** (ils opèrent après la
génération).

---

## 1. Commentaire produit, avec ses références

Indicateur : « Répartition du stock de PME en 2023 par région », exercice 2023.

> • Pour l'exercice 2023, Stock des PME | 2018 s'établit à **255 059**.
>    ↳ source : annuaire_2023, exercice 2023, tableau apparié [donnée]
> • Pour l'exercice 2023, Stock des PME | 2019 (e) s'établit à **287 376**.
>    ↳ source : annuaire_2023, exercice 2023, tableau apparié [donnée]
> …

**Exactitude : 1,00** (toutes les valeurs proviennent du tableau de l'exercice).
Chaque proposition porte sa **référence** (affichage clé n°1).

## 2. Le même, sans ancrage documentaire (C0)

Sans les commentaires homologues antérieurs, la génération ne dispose plus du
« patron » de rédaction : elle énumère les valeurs sans en reprendre la forme.
C'est ce que mesure l'écart C1 ≫ C0 (+0,163 de ROUGE-1, cf. chapitre 4).

## 3. Contrôle — une valeur d'un commentaire antérieur est écartée

Brouillon citant **393 166** (valeur annoncée par un rapport antérieur), alors
que l'Annuaire de l'exercice indique 393 175 (estimation révisée) :

> ✗ ÉCARTÉE (valeur non sourcée ['393166']) : « Le stock de PME atteint 393 166 unités. »

Exactitude 0,00 → la proposition est **retirée** (affichage clé n°2). C'est la
règle de portée : une valeur ne vaut que si elle figure dans le bloc de données
de l'exercice, jamais parce qu'un commentaire passé la mentionnait.

## 4. Contrôle — une valeur inventée est écartée

> ✗ ÉCARTÉE (valeur non sourcée ['5,9']) : « La croissance atteint 5,9 %. »

Le bloc de données ne contient que 2,4 % : la valeur inventée est **retirée**.

## 5. Abstention — indicateur hors périmètre

> ⚠ Abstention : aucun tableau apparié ou aucune valeur pour l'exercice.

Sans tableau apparié ni valeurs, le système **s'abstient** plutôt que de fonder
un commentaire sur rien (affichage clé n°3).

---

## Propriétés démontrées (cahier des charges §0)

| # | Propriété | Temps |
|---|-----------|-------|
| 1 | Ne peut pas se tromper sur un chiffre | 1, 3, 4 |
| 2 | Le patron vient du passé, les valeurs du présent | 1, 2, 3 |
| 3 | Aucune information postérieure à l'exercice | (filtrage temporel, testé) |
| 4 | Chaque énoncé sourcé ; s'abstient sinon | 1, 5 |
