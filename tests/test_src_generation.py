"""
Tests de génération contrainte (cahier des charges, Étape 6) en régime dégradé
(sans LLM) : la chaîne contexte → prompt → génération → propositions → garde-fous
fonctionne de bout en bout et reste 100 % ancrée dans les données.
"""
from __future__ import annotations

from src.retrieval.store import Store, PassageRow, ValeurRow
from src.retrieval.context import assembler_contexte
from src.generation.prompt import construire_prompt
from src.generation.generate import generer
from src.guards.numeric import controler_propositions


def _store():
    s = Store(":memory:")
    for ex in (2022, 2023):
        s.add_document(f"ann{ex}", "annuaire", ex)
        s.add_appariement("stock-region", ex, 1, 4)
    s.add_valeur(ValeurRow(exercice=2023, ligne="Centre", colonne="stock",
                           valeur="393 175", tableau_n=4))
    s.add_valeur(ValeurRow(exercice=2023, ligne="Littoral", colonne="stock",
                           valeur="26 769", tableau_n=4))
    s.add_passage(PassageRow(exercice=2022, code_indicateur="stock-region",
                             texte="Le stock de PME progresse de 12,3 % sur la période, "
                                   "porté par la région du Centre."))
    s.commit()
    return s


def test_prompt_cinq_blocs_et_regles_repetees():
    s = _store()
    ctx = assembler_contexte(s, "stock-region", 2023)
    p = construire_prompt(ctx, "Répartition du stock de PME par région")
    assert "RÈGLES DE RESTITUTION" in p
    # Règles répétées : au moins deux occurrences (après le bloc d'exemples).
    assert p.count("RÈGLES DE RESTITUTION") >= 2
    assert "CONSIGNE DE SORTIE" in p
    assert "VALEURS DE L'EXERCICE 2023" in p


def test_generation_degradee_est_ancree():
    s = _store()
    ctx = assembler_contexte(s, "stock-region", 2023)
    res = generer(ctx, "Répartition du stock de PME par région")
    assert res.regime.startswith("dégradé")
    assert res.propositions
    # Toutes les valeurs citées proviennent du bloc de données -> exactitude 1.
    audit = controler_propositions(res.propositions, ctx.bloc_donnees())
    assert audit.exactitude == 1.0
    assert len(audit.ecartees) == 0


def test_forme_anterieure_sans_valeurs():
    """La phrase d'interprétation reprend la forme d'un commentaire antérieur
    mais AUCUNE de ses valeurs (12,3 % ne doit pas réapparaître)."""
    s = _store()
    ctx = assembler_contexte(s, "stock-region", 2023)
    res = generer(ctx, "Répartition du stock de PME par région")
    assert "12,3" not in res.texte_brut
