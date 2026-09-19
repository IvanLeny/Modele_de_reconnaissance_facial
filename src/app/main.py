"""
Interface Streamlit (cahier des charges, Étape 10).

Trois espaces seulement — aucune fonctionnalité ajoutée (ni authentification, ni
tableau de bord, ni historique) :
  1. Ingestion d'un document (état du corpus ingéré) ;
  2. Génération d'un commentaire (cœur de l'outil) ;
  3. Export des commentaires validés.

Trois affichages portent les garanties du dispositif :
  - la référence attachée à chaque proposition ;
  - le signalement visible d'une proposition écartée par le contrôle des valeurs ;
  - le message d'abstention, explicite quant à sa cause.

Aucun commentaire ne quitte le système sans validation humaine : l'agent
accepte, corrige ou rejette chaque proposition avant l'export.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Bootstrap du chemin d'import (permet « streamlit run src/app/main.py »).
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ingestion.ingest import build_store            # noqa: E402
from src.retrieval.context import assembler_contexte    # noqa: E402
from src.generation.generate import generer             # noqa: E402
from src.guards.numeric import controler_propositions   # noqa: E402
from src.guards.abstention import decider               # noqa: E402
from src.guards.provenance import tracer, SourceRef     # noqa: E402

st.set_page_config(page_title="MINPMEESA — Assistant de commentaires", layout="wide")


@st.cache_resource
def charger():
    return build_store(verbose=False)


@st.cache_resource
def charger_complet():
    """Base complète (18 documents) pour la note de perspective."""
    from src.retrieval.store import Store
    from src.ingestion.ingest import populate_all
    s = Store(":memory:")
    populate_all(s)
    return s


store, ref = charger()
onglet = st.sidebar.radio("Espace", ["Ingestion", "Génération",
                                     "Note de perspective", "Export validé"])

if "valides" not in st.session_state:
    st.session_state["valides"] = []

# --------------------------------------------------------------------------- #
if onglet == "Ingestion":
    import os
    import tempfile
    st.header("Espace 1 — Ingestion d'un document")
    exercices = sorted({e for (e, _) in ref.reference})
    st.write(f"**{len(ref.reference)}** unités évaluables (indicateur × exercice), "
             f"exercices {exercices}.")

    st.subheader("Ajouter un document à la base")
    persistant = bool(os.environ.get("RAG_PG_DSN"))
    st.caption("Base persistante PostgreSQL détectée : l'ajout est durable."
               if persistant else
               "Mode session (SQLite en mémoire) : l'ajout vaut pour cette session. "
               "Définissez RAG_PG_DSN pour un ajout persistant en base PostgreSQL.")
    up = st.file_uploader("Déposer un PDF (annuaire, rapport, note, contexte)", type="pdf")
    if up is not None and st.button("Ingérer ce document"):
        from src.ingestion.ingest import ingest_document
        tmp = os.path.join(tempfile.gettempdir(), up.name)
        with open(tmp, "wb") as f:
            f.write(up.getbuffer())
        try:
            if persistant:
                from src.retrieval.pg_store import PostgresStore
                cible = PostgresStore(os.environ["RAG_PG_DSN"])
                cible.create_schema()
            else:
                cible = store
            added = ingest_document(cible, tmp, verbose=False)
            st.success(f"Document ajouté : **{added['doc_id']}** — type *{added['type']}*, "
                       f"exercice {added['exercice']}, +{added['valeurs']} valeurs, "
                       f"+{added['passages']} passages.")
            if persistant:
                st.write("Contenu de la base :", cible.compter())
        except Exception as e:
            st.error(f"Échec de l'ingestion : {type(e).__name__} : {e}")

    st.divider()
    st.caption("Les valeurs proviennent des Annuaires ; les commentaires de "
               "référence, des Rapports d'analyse (segmentés par graphique).")

# --------------------------------------------------------------------------- #
elif onglet == "Génération":
    st.header("Génération d'un commentaire")
    exercices = sorted({e for (e, _) in ref.reference})
    ex = st.selectbox("Exercice", exercices, index=len(exercices) - 1)
    indics = [(c, ref.intitule[(ex, c)]) for (e, c) in ref.reference if e == ex]
    if not indics:
        st.info("Aucun indicateur pour cet exercice.")
    else:
        libelle = st.selectbox("Indicateur", [i[1] for i in indics])
        code = next(c for c, lib in indics if lib == libelle)
        if st.button("Générer"):
            ctx = assembler_contexte(store, code, ex, intitule=libelle)
            src = SourceRef(doc_id=f"annuaire_{ex}", exercice=ex, section="tableau apparié")
            d = decider(ctx.bloc_donnees(), ctx.commentaires_anterieurs,
                        min_confiance=0.25, tableau_apparie=bool(ctx.valeurs_n))
            if d.abstention:
                st.warning(f"⚠ Abstention : {d.motif}")   # affichage clé n°3
            else:
                res = generer(ctx, libelle)
                st.caption(f"Régime : {res.regime}")
                audit = controler_propositions(res.propositions, ctx.bloc_donnees())
                st.subheader("Propositions retenues")
                for i, a in enumerate(audit.retenues):
                    t = tracer(a.proposition, src)
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        txt = st.text_area(f"prop_{i}", a.proposition.texte,
                                           label_visibility="collapsed", key=f"txt_{ex}_{i}")
                        st.caption(f"↳ {t.source.libelle()} [{t.niveau}]")  # affichage clé n°1
                    with col2:
                        if st.checkbox("Valider", key=f"val_{ex}_{i}"):
                            st.session_state["valides"].append({"exercice": ex,
                                "indicateur": libelle, "texte": txt})
                if audit.ecartees:
                    st.subheader("Propositions écartées par le contrôle des valeurs")
                    for a in audit.ecartees:                                  # affichage clé n°2
                        st.error(f"✗ Valeur non sourcée {a.valeurs_non_soutenues} — "
                                 f"« {a.proposition.texte} »")

# --------------------------------------------------------------------------- #
elif onglet == "Note de perspective":
    from src.generation.perspective import generer_note
    st.header("Note d'analyse de perspective — aide à la décision")
    st.caption("Synthèse transversale de TOUT le corpus (annuaires, rapports, "
               "notes de conjoncture, contexte), sous les mêmes garde-fous : "
               "chiffres cités littéralement, sources attachées, abstention sinon.")
    exs = sorted({e for (e, _) in ref.reference})
    ex = st.selectbox("Exercice de référence", exs, index=len(exs) - 1)
    if st.button("Produire la note"):
        note = generer_note(charger_complet(), ex)
        st.caption(f"Régime : {note.regime} — sources : {', '.join(note.sources)}")
        st.markdown(note.texte)
        if note.audit is not None and note.audit.ecartees:
            st.subheader("Valeurs écartées par le contrôle")
            for a in note.audit.ecartees:
                st.error(f"✗ {a.valeurs_non_soutenues} — « {a.proposition.texte[:120]} »")
        st.download_button("Exporter la note (Markdown)", note.texte,
                           file_name=f"note_perspective_{ex}.md")

# --------------------------------------------------------------------------- #
elif onglet == "Export validé":
    st.header("Commentaires validés")
    valides = st.session_state["valides"]
    if not valides:
        st.info("Aucun commentaire validé pour l'instant. "
                "Validez des propositions dans l'espace Génération.")
    else:
        for v in valides:
            st.markdown(f"**{v['indicateur']}** (exercice {v['exercice']}) — {v['texte']}")
        txt = "\n".join(f"[{v['exercice']}] {v['indicateur']} : {v['texte']}" for v in valides)
        st.download_button("Exporter (texte)", txt, file_name="commentaires_valides.txt")
