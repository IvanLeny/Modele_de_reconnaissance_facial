"""
Tests d'appariement (cahier des charges, Étape 3). Le code indicateur est stable
d'une édition à l'autre ; le kappa de la double saisie se calcule correctement.
"""
from __future__ import annotations

from src.pairing.build import code_indicateur, Appariement
from src.pairing.schema import coherence_report, cohen_kappa


def test_code_indicateur_stable_entre_editions():
    """Le même indicateur, exprimé pour 2023 puis 2024, reçoit le même code
    (l'année et les unités sont neutralisées)."""
    c23 = code_indicateur("Répartition du stock de PME en 2023 par région (en %)")
    c24 = code_indicateur("Répartition du stock de PME en 2024 par région (en %)")
    assert c23 == c24


def test_coherence_multi_editions():
    pairs = [
        Appariement("stock-region", 2023, 1, "…", 4, "…", 0.6),
        Appariement("stock-region", 2024, 1, "…", 3, "…", 0.6),
        Appariement("oes-crees", 2023, 8, "…", 7, "…", 0.2),
    ]
    rep = coherence_report(pairs)
    assert rep["n_codes_multi_editions"] == 1
    assert "stock-region" in rep["codes_multi_editions"]


def test_cohen_kappa_accord_parfait():
    a = {(2023, 1): 4, (2023, 2): 1}
    b = {(2023, 1): 4, (2023, 2): 1}
    kappa, n, acc = cohen_kappa(a, b)
    assert n == 2 and acc == 2 and kappa == 1.0


def test_cohen_kappa_desaccord():
    a = {(2023, 1): 4, (2023, 2): 1, (2023, 3): 5}
    b = {(2023, 1): 4, (2023, 2): 2, (2023, 3): 5}   # désaccord sur le graphique 2
    kappa, n, acc = cohen_kappa(a, b)
    assert n == 3 and acc == 2 and kappa < 1.0
