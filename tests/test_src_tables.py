"""
Tests de linéarisation des tableaux (cahier des charges, Étape 2).

Vérifient la propriété essentielle : chaque valeur conserve ses en-têtes de
ligne et de colonne (aucune valeur orpheline), y compris pour un en-tête à
plusieurs niveaux (exercice + unité). Indépendant du corpus.
"""
from __future__ import annotations

from src.ingestion.tables import linearize_table, _is_data_value


def test_valeur_porte_ligne_et_colonne():
    """Tableau simple : secteur × exercice."""
    rows = [
        ["Secteur", "2022", "2023"],
        ["Tertiaire", "79,6", "80,1"],
        ["Primaire", "0,13", "0,10"],
    ]
    t = linearize_table(rows, page=1)
    enonces = {c.enonce() for c in t.cellules}
    assert "Tertiaire | 2022 = 79,6" in enonces
    assert "Primaire | 2023 = 0,10" in enonces
    # Aucune valeur orpheline : toutes ont une ligne et une colonne non vides.
    assert all(c.ligne and c.colonne and c.valeur for c in t.cellules)
    # Le millésime n'est jamais restitué comme une valeur de donnée.
    assert all(c.valeur not in ("2022", "2023") for c in t.cellules)


def test_entete_multi_niveaux():
    """En-tête à deux niveaux : l'exercice ET l'unité doivent apparaître."""
    rows = [
        ["Secteur", "2016", "", "2023", ""],
        ["", "Effectif", "%", "Effectif", "%"],
        ["Primaire", "342", "0,17", "377", "0,10"],
    ]
    t = linearize_table(rows, page=1)
    enonces = {c.enonce() for c in t.cellules}
    # La valeur 342 est reliée à l'exercice 2016 et à l'unité Effectif.
    cible = next(c for c in t.cellules if c.valeur == "342")
    assert "2016" in cible.colonne and "Effectif" in cible.colonne
    assert cible.ligne == "Primaire"
    # 0,10 relié à 2023 et % .
    c2 = next(c for c in t.cellules if c.valeur == "0,10")
    assert "2023" in c2.colonne and "%" in c2.colonne


def test_millesime_n_est_pas_une_valeur():
    assert _is_data_value("342") is True
    assert _is_data_value("0,17") is True
    assert _is_data_value("79,6 %") is True
    assert _is_data_value("2016") is False
    assert _is_data_value("2023 (e)") is False
