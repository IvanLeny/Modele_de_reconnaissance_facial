"""
Tests d'ingestion (démarche §1) : segmentation, linéarisation/repérage des
tableaux, exclusion des formulaires vides, et lecture des paramètres depuis
config.yaml. Aucune dépendance réseau.
"""
from __future__ import annotations

from rag_minpmeesa.config import get_settings, IngestionConfig
from rag_minpmeesa.schema import DocumentMeta
from rag_minpmeesa.ingestion.extract import PageElement
from rag_minpmeesa.ingestion.chunk import (
    chunk_document, compute_informativeness, _is_empty_form)


def _meta():
    return DocumentMeta(doc_id="doc_test", title="Document de test",
                        source_file="doc_test.pdf", doc_type="document")


def test_segmentation_respecte_les_bornes():
    """Les passages produits respectent la taille cible et le minimum de mots."""
    cfg = IngestionConfig(chunk_size_words=40, chunk_overlap_words=10, min_chunk_words=5)
    texte = "mot " * 200  # 200 mots de prose
    el = [PageElement(page=1, text=texte.strip(), section="Section 1", is_table=False)]
    chunks = chunk_document(el, _meta(), cfg)
    assert len(chunks) >= 3
    assert all(c.word_count >= cfg.min_chunk_words for c in chunks)
    assert all(c.word_count <= cfg.chunk_size_words + 5 for c in chunks)
    assert all(c.doc_id == "doc_test" and c.page_start == 1 for c in chunks)


def test_tableau_reste_d_un_seul_tenant():
    """Un tableau chiffré compact n'est pas scindé et est marqué comme tabulaire."""
    cfg = IngestionConfig(chunk_size_words=180, min_chunk_words=5, table_max_words=320)
    tableau = ("Tableau 1 : Stock des PME par région "
               "Adamaoua 11 402 2,9 Centre 12 581 3,2 Yaoundé 93 967 23,9 "
               "Est 13 761 3,5 Littoral 26 769 6,8 Total 393 166 100,0")
    el = [PageElement(page=5, text=tableau, section="1.1", is_table=True)]
    chunks = chunk_document(el, _meta(), cfg)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.is_table and c.contains_numbers
    # La correspondance en-tête / valeur est préservée dans le même passage.
    assert "Yaoundé" in c.text and "93 967" in c.text


def test_formulaire_vide_est_ecarte():
    """Un canevas d'intitulés sans données chiffrées est reconnu comme vide."""
    form = ("Nombre de PME restructurées Nombre de PME évaluées Nombre de PME "
            "sensibilisées Effectif Total Autres à préciser Montant total")
    assert _is_empty_form(form) is True
    # Une vraie ligne de données ne l'est pas.
    assert _is_empty_form("Total PME 202 746 287 376 349 722 393 166") is False


def test_informativite_separe_prose_donnees_et_creux():
    prose = ("La perception des chefs d'entreprises sur l'évolution de leurs "
             "activités est moins bonne ce trimestre par rapport au précédent.")
    creux = "Nombre de Total Effectif Autres à préciser"
    assert compute_informativeness(prose) > 0.8
    assert compute_informativeness(creux) < 0.5


def test_parametres_lus_depuis_config_yaml():
    """Les valeurs proviennent de config.yaml, pas de constantes en dur."""
    s = get_settings()
    assert s.retrieval.rrf_k == 60
    assert s.expansion.enabled in (True, False)
    assert 0.0 <= s.abstention.min_score <= 1.0


def test_expansion_lexicale_declenche_les_synonymes():
    """L'expansion relie « effectif » aux formulations « nombre / total » (§4)."""
    from rag_minpmeesa.retrieval.expansion import QueryExpander
    fam = [["effectif", "effectifs", "nombre", "total", "stock"],
           ["pme", "petites et moyennes entreprises"]]
    exp = QueryExpander(fam, max_expansions_per_term=4)
    out = exp.expand("effectif des entreprises").split()
    assert "nombre" in out and "total" in out
    # Une famille non déclenchée n'ajoute rien.
    assert "petites" not in exp.expand("effectif").split()
