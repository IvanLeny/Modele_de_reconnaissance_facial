"""
Tests des garde-fous (cahier des charges, Étape 7). Indépendants du LLM et du
corpus : ils valident les critères d'acceptation sur des exemples contrôlés.
"""
from __future__ import annotations

from src.guards.numeric import (
    normalize_number, extract_numbers, number_supported,
    controler_propositions, Proposition)


# --- Règle 1 : normalisation ------------------------------------------------ #
def test_normalisation_separateurs():
    assert normalize_number("393 954") == normalize_number("393954")
    assert normalize_number("79,6 %") == normalize_number("79.6")


# --- Règle 2 : millésimes exclus -------------------------------------------- #
def test_millesime_exclu_de_l_extraction():
    nums = extract_numbers("En 2023, le stock atteint 393 954 entreprises.")
    assert "393954" in nums
    assert "2023" not in nums


# --- Règle 3 : pas de recalcul ---------------------------------------------- #
def test_valeur_derivee_refusee():
    data = "Total 393 954 entreprises dont 393 166 PME."
    # 788 (une somme/dérivée) n'est pas écrite telle quelle -> non soutenue.
    assert number_supported("393 954", data) is True
    assert number_supported("787120", data) is False


# --- Règle 4 : portée = bloc de données, jamais commentaires antérieurs ------ #
def test_valeur_d_un_commentaire_anterieur_ecartee():
    """Le rapport 2023 annonçait 393 166 PME ; l'Annuaire contemporain indique
    393 175. Une proposition citant 393 166 (valeur d'un commentaire antérieur)
    doit être écartée si le bloc de données ne contient que 393 175."""
    data_block = "Nombre de PME en 2023 : 393 175."
    props = [
        Proposition("Le stock de PME s'établit à 393 175 unités.", "T1"),
        Proposition("Le stock de PME atteint 393 166 unités.", "C_ant"),  # valeur antérieure
    ]
    audit = controler_propositions(props, data_block)
    retenus = {a.proposition.texte for a in audit.retenues}
    ecartes = {a.proposition.texte for a in audit.ecartees}
    assert "Le stock de PME s'établit à 393 175 unités." in retenus
    assert "Le stock de PME atteint 393 166 unités." in ecartes


def test_valeur_inventee_ecartee():
    data_block = "Croissance de la zone CEMAC : 2,4 % au 1er trimestre 2025."
    props = [
        Proposition("La croissance CEMAC est de 2,4 %.", "T1"),
        Proposition("La croissance CEMAC atteint 5,9 %.", "T2"),   # inventée
    ]
    audit = controler_propositions(props, data_block)
    assert len(audit.retenues) == 1 and len(audit.ecartees) == 1
    assert audit.ecartees[0].valeurs_non_soutenues == ["5,9"]


def test_exactitude_bornee():
    data_block = "3,9 % après 3,2 %."
    props = [Proposition("Hausse de 3,9 % contre 3,2 %.", "T1")]
    audit = controler_propositions(props, data_block)
    assert audit.exactitude == 1.0
    assert 0.0 <= audit.exactitude <= 1.0


# --- Provenance (Étape 7.2) ------------------------------------------------- #
def test_provenance_donnee_vs_interpretation():
    from src.guards.provenance import tracer, SourceRef
    src_data = SourceRef(doc_id="annuaire_2023", exercice=2023, section="Tableau 4", page=16)
    com = [("La perception des chefs d'entreprise s'améliore ce trimestre.",
            SourceRef(doc_id="rapport_analyse_2022", exercice=2022))]
    p_val = Proposition("Le stock atteint 393 175 PME.", "T1")
    p_int = Proposition("La perception des chefs d'entreprise s'améliore.", "I1")
    t_val = tracer(p_val, src_data, com)
    t_int = tracer(p_int, src_data, com)
    assert t_val.niveau == "donnée" and "annuaire_2023" in t_val.source.libelle()
    assert t_int.niveau == "interprétation" and "rapport_analyse_2022" in t_int.source.libelle()


# --- Abstention (Étape 7.3) ------------------------------------------------- #
def test_abstention_sans_valeurs():
    from src.guards.abstention import decider
    d = decider(data_block="", commentaires_anterieurs=["x y z"], min_confiance=0.3)
    assert d.abstention and "aucun tableau" in d.motif


def test_abstention_contexte_faible():
    from src.guards.abstention import decider
    d = decider(data_block="Stock 393 175 PME en 2023.",
                commentaires_anterieurs=[], min_confiance=0.3)
    assert d.abstention and "trop faible" in d.motif


def test_pas_d_abstention_si_contexte_suffisant():
    from src.guards.abstention import decider
    com = ["La perception des chefs d'entreprise sur l'évolution de leurs "
           "activités s'améliore nettement au cours de ce trimestre par rapport "
           "au précédent selon l'enquête."]
    d = decider(data_block="Stock 393 175 PME en 2023.",
                commentaires_anterieurs=com, min_confiance=0.3)
    assert not d.abstention
