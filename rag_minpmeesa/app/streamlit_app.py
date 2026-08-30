"""
Application web du prototype (chapitre 3.7) — Streamlit.

Deux modes d'usage sélectionnables (production / consultation), interrogation en
langage naturel, restitution ancrée avec passages sources dépliables et tableau
de bord des contrôles qualité (exactitude chiffrée, fidélité, cloisonnement).

Lancement :
    streamlit run rag_minpmeesa/app/streamlit_app.py
"""
from __future__ import annotations

import streamlit as st

from rag_minpmeesa.config import Mode, get_settings
from rag_minpmeesa.engine import RAGEngine
from rag_minpmeesa.retrieval.pipeline import CONFIGS
from rag_minpmeesa.retrieval.filters import Filter
from rag_minpmeesa.config import DiffusionStatus


st.set_page_config(page_title="RAG MINPMEESA", page_icon="📊", layout="wide")


@st.cache_resource(show_spinner="Chargement de l'index…")
def load_engine():
    eng = RAGEngine()
    return eng.ensure_ready()


def main():
    st.title("📊 Assistant documentaire RAG — MINPMEESA")
    st.caption("Exploitation du patrimoine documentaire en appui à l'Annuaire "
               "statistique et au Rapport annuel de performance. "
               "Mémoire M2 MDSMS — Adnane MAMA IDISSA, ISSEA-CEMAC.")

    engine = load_engine()

    # -------- Barre latérale : mode et options -------- #
    with st.sidebar:
        st.header("Mode d'usage")
        mode_label = st.radio(
            "Sélectionner le mode",
            ["Production (agents — corpus interne + publié)",
             "Consultation (décideurs — publié uniquement)"],
        )
        mode = Mode.PRODUCTION if mode_label.startswith("Production") else Mode.CONSULTATION

        st.header("Configuration de récupération")
        config_name = st.selectbox("Étage de récupération",
                                   list(CONFIGS.keys()), index=3)

        st.header("Filtres (métadonnées)")
        types = st.multiselect("Type de document",
                               ["annuaire_statistique", "note_conjoncture"])
        years = st.multiselect("Année", [2022, 2024, 2025])
        st.divider()
        st.subheader("Index")
        st.json(engine.store.meta, expanded=False)
        if mode == Mode.CONSULTATION:
            st.info("🔒 Cloisonnement actif : les documents internes non validés "
                    "sont inaccessibles dans ce mode.")

    # -------- Zone principale : requête -------- #
    query = st.text_input("Votre question",
                          placeholder="Ex. : Quelle est la répartition des PME par région en 2023 ?")
    col1, col2 = st.columns([1, 5])
    ask = col1.button("Interroger", type="primary")

    if ask and query.strip():
        base = Filter()
        if types:
            base.doc_types = set(types)
        if years:
            base.years = set(years)

        run = CONFIGS[config_name]
        results = engine.retrieve(query, mode=mode, run=run, base_filter=base)
        ans = engine.answerer.answer(query, results, mode=mode)

        if ans.refused:
            st.warning(ans.message)
            return

        # Synthèse sourcée
        st.subheader("Synthèse (données chiffrées reprises littéralement)")
        for s in ans.sentences:
            st.markdown(f"- {s.text}  \n  <small><i>{s.citation}</i></small>",
                        unsafe_allow_html=True)

        # Contrôles qualité
        st.subheader("Contrôles qualité")
        m1, m2, m3 = st.columns(3)
        m1.metric("Exactitude chiffrée",
                  f"{ans.numeric_audit.accuracy:.0%}",
                  f"{ans.numeric_audit.supported}/{ans.numeric_audit.total} nombres")
        m2.metric("Fidélité",
                  f"{ans.faithfulness.faithfulness:.0%}",
                  f"{ans.faithfulness.n_supported}/{ans.faithfulness.n_sentences} énoncés")
        m3.metric("Sources citées", str(len(ans.sources)))
        if ans.numeric_audit.unsupported:
            st.error("Nombres non sourcés retirés par le garde-fou : "
                     + ", ".join(ans.numeric_audit.unsupported))

        # Passages sources
        st.subheader("Passages sources")
        for b in ans.context:
            status = b.result.chunk.diffusion_status.value
            tag = "🔒 interne" if status == "interne" else "publié"
            with st.expander(f"[{b.sid}] {b.citation}  ·  {tag}"):
                st.write(b.text)
                st.caption(
                    f"doc_id={b.result.chunk.doc_id} · "
                    f"pages {b.result.chunk.page_start}-{b.result.chunk.page_end} · "
                    f"rerank={b.result.score_rerank}")


if __name__ == "__main__":
    main()
