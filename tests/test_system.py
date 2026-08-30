"""
Tests unitaires et d'intégration du système RAG (support du chapitre 3).

Ils vérifient les propriétés *de conception* qui font la valeur du travail :
  - la règle de citation littérale des données chiffrées (garde-fou numérique) ;
  - le cloisonnement des deux modes (aucune fuite du corpus interne) ;
  - la correction des briques de récupération (RRF) et des métriques d'évaluation.

Lancement : pytest -q
"""
from __future__ import annotations

import pytest

from rag_minpmeesa.config import Mode, DiffusionStatus, get_settings
from rag_minpmeesa.generation.numeric import (
    extract_numbers, number_supported, audit_numbers)
from rag_minpmeesa.retrieval.fusion import reciprocal_rank_fusion
from rag_minpmeesa.evaluation.metrics import (
    ndcg_at_k, mrr, precision_at_k, recall_at_k)


# --------------------------------------------------------------------------- #
#  Traitement des données chiffrées (chapitre 3.6)
# --------------------------------------------------------------------------- #
def test_extract_numbers_formats():
    text = "Le stock est de 393 954 entreprises, dont 75,95% dans le tertiaire (3.2)."
    nums = {n.canonical for n in extract_numbers(text)}
    assert "393 954" in nums
    assert "75,95" in nums


def test_number_supported_literal_match():
    src = ["Plus de 69,80% des PME déclarent une trésorerie difficile."]
    m = extract_numbers("69,80%")[0]
    assert number_supported(m, src) is True


def test_number_supported_rejects_absent_value():
    src = ["Plus de 69,80% des PME déclarent une trésorerie difficile."]
    m = extract_numbers("70%")[0]        # valeur différente -> non soutenue
    assert number_supported(m, src) is False


def test_number_supported_thousands_equivalence():
    src = ["Le stock est estimé à 393954 entreprises."]
    m = extract_numbers("393 954")[0]    # même valeur, séparateur différent
    assert number_supported(m, src) is True


def test_audit_numbers_accuracy():
    src = ["La croissance atteint 3,9% après 3,2% en 2023."]
    audit = audit_numbers("La croissance est de 3,9% (contre 3,2%).", src)
    assert audit.total == 2
    assert audit.all_supported
    assert audit.accuracy == 1.0


# --------------------------------------------------------------------------- #
#  Fusion RRF (chapitre 3.4)
# --------------------------------------------------------------------------- #
def test_rrf_combines_channels():
    lex = [(1, 5.0), (2, 4.0), (3, 3.0)]
    vec = [(2, 0.9), (3, 0.8), (4, 0.7)]
    fused = reciprocal_rank_fusion({"lexical": lex, "vector": vec}, k=60)
    # Le passage 2 (bien classé par les deux canaux) domine.
    best = max(fused.items(), key=lambda kv: kv[1]["rrf"])[0]
    assert best == 2


# --------------------------------------------------------------------------- #
#  Métriques d'évaluation (chapitre 4)
# --------------------------------------------------------------------------- #
def test_metrics_perfect_ranking():
    rels = [True, True, False, False]
    assert precision_at_k(rels, 2) == 1.0
    assert mrr(rels) == 1.0
    assert ndcg_at_k(rels, 5, total_relevant=2) == pytest.approx(1.0)


def test_metrics_bounds():
    rels = [False, False, True]
    assert 0.0 <= ndcg_at_k(rels, 5, 1) <= 1.0
    assert mrr(rels) == pytest.approx(1 / 3)
    assert recall_at_k(rels, 5, total_relevant=1) == 1.0


# --------------------------------------------------------------------------- #
#  Cloisonnement des modes (chapitre A.2) — intégration
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def engine():
    from rag_minpmeesa.engine import RAGEngine
    return RAGEngine().ensure_ready()


def test_consultation_never_returns_internal(engine):
    """En mode consultation, aucun passage interne ne doit être renvoyé."""
    for q in ["conjoncture premier trimestre 2025",
              "mesures d'appui aux PME 2025",
              "taux de couverture enquête PME"]:
        hits = engine.retrieve(q, mode=Mode.CONSULTATION, top_k=10)
        assert all(h.chunk.diffusion_status == DiffusionStatus.PUBLIE for h in hits)


def test_production_can_reach_internal(engine):
    """En mode production, le corpus interne est bien accessible."""
    hits = engine.retrieve("appui 200 entreprises 1er trimestre 2025",
                           mode=Mode.PRODUCTION, top_k=10)
    assert any(h.chunk.diffusion_status == DiffusionStatus.INTERNE for h in hits)


def test_answer_numeric_guardrail(engine):
    """Toute donnée chiffrée de la réponse est sourcée (exactitude = 1)."""
    ans = engine.query("trésorerie difficile des PME au 2e trimestre 2024",
                       mode=Mode.PRODUCTION)
    assert not ans.refused
    assert ans.numeric_audit.accuracy == 1.0
