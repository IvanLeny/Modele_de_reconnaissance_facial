"""
Tests des métriques d'évaluation (cahier des charges, Étape 8).
Bornes théoriques respectées (§6.4) et comportements attendus.
"""
from __future__ import annotations

from src.eval.metrics import (
    rouge_n, rouge_l, similarite_lexicale, taux_soutenu, couverture)


def test_rouge_identique_vaut_un():
    t = "le stock de pme augmente en 2023"
    assert rouge_n(t, t, 1) == 1.0
    assert rouge_l(t, t) == 1.0


def test_rouge_borne():
    a = "croissance des pme dans le tertiaire"
    b = "le tertiaire concentre la croissance des pme et des tpe"
    for v in (rouge_n(a, b, 1), rouge_n(a, b, 2), rouge_l(a, b), similarite_lexicale(a, b)):
        assert 0.0 <= v <= 1.0


def test_rouge_disjoint_vaut_zero():
    assert rouge_n("alpha beta", "gamma delta", 1) == 0.0


def test_taux_soutenu():
    props = ["le stock de pme augmente", "phrase totalement hors sujet xyz"]
    contexte = "le stock de pme augmente fortement dans le tertiaire"
    v = taux_soutenu(props, contexte, seuil=0.5)
    assert 0.0 <= v <= 1.0 and v == 0.5


def test_couverture_bornee():
    assert couverture(3, 10) == 0.3
    assert couverture(20, 10) == 1.0        # jamais > 1
    assert couverture(1, 0) == 0.0
