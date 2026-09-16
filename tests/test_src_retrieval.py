"""
Tests de récupération (cahier des charges, Étape 5).

Vérifient le critère d'acceptation central : le **filtrage temporel** empêche
tout passage d'exercice ≥ N de remonter, et le contexte est bien scindé en trois
blocs. Indépendant du LLM. Utilise le dépôt SQLite en mémoire.
"""
from __future__ import annotations

from src.retrieval.store import Store, PassageRow, ValeurRow
from src.retrieval.context import assembler_contexte


def _store():
    s = Store(":memory:")
    for ex in (2021, 2022, 2023, 2024):
        s.add_document(f"rap{ex}", "rapport_analyse", ex)
        s.add_document(f"ann{ex}", "annuaire", ex)
        s.add_passage(PassageRow(exercice=ex, code_indicateur="stock-region",
                                 texte=f"Commentaire régional de l'exercice {ex}.",
                                 doc_id=f"rap{ex}"))
        s.add_valeur(ValeurRow(exercice=ex, ligne="Centre", colonne="stock",
                               valeur=str(1000 + ex), doc_id=f"ann{ex}", tableau_n=4))
        s.add_appariement("stock-region", ex, graphique_n=1, tableau_n=4)
    s.commit()
    return s


def test_filtrage_temporel_exclut_posterieur():
    """Pour l'exercice 2023, aucun commentaire de 2023 ni 2024 ne doit remonter."""
    s = _store()
    coms = s.commentaires_anterieurs("stock-region", 2023)
    exercices = {c["exercice"] for c in coms}
    assert exercices == {2021, 2022}
    assert 2023 not in exercices and 2024 not in exercices


def test_filtrage_temporel_sur_tout_le_corpus_simule():
    """Sur chaque exercice, le max des exercices remontés est < N (propriété
    vérifiée pour tous les N, pas seulement un cas)."""
    s = _store()
    for n in (2021, 2022, 2023, 2024):
        coms = s.commentaires_anterieurs("stock-region", n)
        assert all(c["exercice"] < n for c in coms)


def test_contexte_trois_blocs():
    s = _store()
    ctx = assembler_contexte(s, "stock-region", 2023)
    # Bloc de données = valeurs de 2023 uniquement.
    assert any("2023" not in v for v in ctx.valeurs_n)  # les valeurs existent
    assert ctx.valeurs_n and ctx.valeurs_anterieures and ctx.commentaires_anterieurs
    # Le bloc de données ne contient que la valeur de l'exercice N (1000+2023=3023).
    assert "3023" in ctx.bloc_donnees()
    assert "3024" not in ctx.bloc_donnees()      # valeur de 2024 jamais dans le bloc N
    # Rendu étiqueté présent.
    assert "VALEURS DE L'EXERCICE 2023" in ctx.rendu()
