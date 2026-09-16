"""
Tests d'ingestion du NOUVEAU prototype (cahier des charges, Étape 1).

Vérifient le critère d'acceptation le plus sensible : l'exercice et le type de
chaque document sont correctement identifiés à partir du CONTENU, malgré les
pièges du corpus (noms de fichiers trompeurs, titres courants erronés).

Ces tests nécessitent les PDF du corpus ; ils sont ignorés si le corpus est
absent, afin de ne pas casser une exécution sans données.
"""
from __future__ import annotations

from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"

# Vérité de terrain établie par analyse du contenu (graphiques/tableaux,
# millésime dominant), cf. docs/JOURNAL.md.
ATTENDU = {
    "annuaire_2022": ("annuaire", 2022),
    "annuaire_2023": ("annuaire", 2023),
    "rapport_analyse_2021": ("rapport_analyse", 2021),
    "rapport_analyse_2022": ("rapport_analyse", 2022),
    "rapport_analyse_2023": ("rapport_analyse", 2023),
    "rapport_analyse_2024": ("rapport_analyse", 2024),
    "note_conjoncture_T1_2024": ("note_conjoncture", 2024),
    "note_conjoncture_T2_2024": ("note_conjoncture", 2024),
    "note_conjoncture_T3_2024": ("note_conjoncture", 2024),
    "note_conjoncture_T1_2025": ("note_conjoncture", 2025),
    "note_conjoncture_T3_2022": ("note_conjoncture", 2022),
    "note_conjoncture_T4_2023": ("note_conjoncture", 2023),
    "contexte_bulletin_2024": ("contexte", None),
    "contexte_bulletin_2023_05": ("contexte", None),
    "contexte_perspective_inflation_2023": ("contexte", None),
    "contexte_perspective_competitivite_pme": ("contexte", None),
}


def _meta(stem):
    from src.ingestion.extract import extract_document
    from src.ingestion.metadata import build_meta
    pdf = CORPUS / f"{stem}.pdf"
    if not pdf.exists():
        pytest.skip(f"corpus absent : {pdf.name}")
    d = extract_document(pdf)
    return build_meta(stem, pdf.name, d.full_text(), len(d.pages))


@pytest.mark.parametrize("stem,attendu", ATTENDU.items())
def test_type_et_exercice(stem, attendu):
    t_attendu, ex_attendu = attendu
    m = _meta(stem)
    assert m.type == t_attendu, f"{stem}: type {m.type} != {t_attendu}"
    if ex_attendu is not None:
        assert m.exercice == ex_attendu, f"{stem}: exercice {m.exercice} != {ex_attendu}"


def test_annuaire_2023_malgre_titre_courant_errone():
    """L'Annuaire d'exercice 2023 porte un titre courant « 2022 » : l'exercice
    doit être relevé sur le contenu, pas sur ce titre courant (§2)."""
    m = _meta("annuaire_2023")
    assert m.exercice == 2023


def test_annuaire_2022_malgre_nom_de_fichier():
    """Le fichier d'origine de l'Annuaire 2022 s'appelait stat2023fr.pdf : le
    millésime du nom de fichier ne doit pas déterminer l'exercice (§2)."""
    m = _meta("annuaire_2022")
    assert m.exercice == 2022
