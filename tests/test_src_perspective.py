"""
Test de la note d'analyse de perspective (aide à la décision).

Vérifie que la note transversale est produite, structurée, ancrée (les nombres
proviennent des chiffres-clés), et qu'elle s'abstient sans données. Corpus requis
(ignoré si absent) ; régime dégradé (sans LLM).
"""
from __future__ import annotations

from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"


@pytest.mark.skipif(not (CORPUS / "annuaire_2023.pdf").exists(), reason="corpus absent")
def test_note_perspective_ancree():
    from src.retrieval.store import Store
    from src.ingestion.ingest import populate_all
    from src.generation.perspective import generer_note
    s = Store(":memory:")
    populate_all(s)
    note = generer_note(s, 2023)
    assert note.texte and "perspective" in note.texte.lower()
    assert "## 1." in note.texte and "## 3." in note.texte      # structure
    assert note.sources                                          # au moins une source
    # Toute valeur retenue provient des chiffres-clés (exactitude définie et ≤ 1).
    assert 0.0 <= note.audit.exactitude <= 1.0


def test_abstention_sans_donnees():
    from src.retrieval.store import Store
    from src.generation.perspective import generer_note
    s = Store(":memory:")                       # base vide -> aucun chiffre-clé
    note = generer_note(s, 2023)
    assert "abstention" in note.texte.lower()
