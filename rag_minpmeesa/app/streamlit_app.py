"""
Application web du prototype (chapitre 3.7) — Streamlit.

Trois usages, une seule interface :
  1. INTERROGER   — poser une question en langage naturel, obtenir une réponse
                    sourcée (deux modes : production / consultation).
  2. COLLECTER    — réunir, par rubrique de l'Annuaire, les données sourcées à
                    transcrire dans l'Annuaire statistique (mode production).
  3. METTRE À JOUR — ajouter, remplacer ou retirer des documents du corpus et
                    reconstruire l'index, sans toucher au code.

Charte visuelle aux couleurs du MINPMEESA ; logo de la structure affiché s'il a
été déposé (dossier app/assets/logo.* ou via l'onglet de mise à jour).

Lancement :
    streamlit run rag_minpmeesa/app/streamlit_app.py
"""
from __future__ import annotations

import os
import sys

# Streamlit exécute ce fichier comme un script isolé : on ajoute la racine du
# projet au chemin d'import avant d'importer le paquet (voir corrections).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import base64

import streamlit as st

from rag_minpmeesa.config import Mode, DiffusionStatus, get_settings
from rag_minpmeesa.engine import RAGEngine
from rag_minpmeesa.retrieval.pipeline import CONFIGS
from rag_minpmeesa.retrieval.filters import Filter
from rag_minpmeesa import admin, collecte


st.set_page_config(page_title="RAG MINPMEESA", page_icon="📊", layout="wide")

# --- Couleurs institutionnelles (inspirées du logo / drapeau camerounais) --- #
VERT = "#0B7A3B"
ROUGE = "#C8102E"
JAUNE = "#F4B400"


@st.cache_resource(show_spinner="Chargement / construction de l'index…")
def load_engine():
    return RAGEngine().ensure_ready()


def reset_engine():
    load_engine.clear()


# --------------------------------------------------------------------------- #
#  Habillage
# --------------------------------------------------------------------------- #
def inject_css():
    st.markdown(f"""
    <style>
      .stApp {{ background: #f7f9f7; }}
      .entete {{
        display:flex; align-items:center; gap:18px;
        background: linear-gradient(120deg, {VERT} 0%, #0e8a44 60%, {VERT} 100%);
        padding:18px 24px; border-radius:14px; color:white;
        box-shadow:0 4px 14px rgba(0,0,0,.12);
        border-bottom:5px solid {JAUNE};
      }}
      .entete h1 {{ font-size:1.55rem; margin:0; color:white; }}
      .entete p  {{ margin:2px 0 0; opacity:.92; font-size:.95rem; }}
      .monogramme {{
        width:64px; height:64px; border-radius:50%;
        background: conic-gradient({ROUGE} 0 33%, {JAUNE} 33% 66%, {VERT} 66% 100%);
        display:flex; align-items:center; justify-content:center;
        font-weight:800; color:white; font-size:.72rem; text-align:center;
        border:3px solid white; box-shadow:0 2px 8px rgba(0,0,0,.2);
      }}
      .badge-mode {{ display:inline-block; padding:3px 12px; border-radius:20px;
        font-size:.8rem; font-weight:700; color:white; }}
      .rep-card {{
        background:white; border-left:6px solid {VERT};
        padding:16px 20px; border-radius:10px; margin-bottom:6px;
        box-shadow:0 2px 8px rgba(0,0,0,.06);
      }}
      .cite {{ color:{VERT}; font-style:italic; font-size:.86rem; }}
      .stButton>button {{
        background:{VERT}; color:white; border:none; border-radius:8px;
        font-weight:600; padding:.5rem 1.1rem;
      }}
      .stButton>button:hover {{ background:{ROUGE}; color:white; }}
      div[data-testid="stMetricValue"] {{ color:{VERT}; }}
      h2, h3 {{ color:{VERT}; }}
    </style>
    """, unsafe_allow_html=True)


def render_header():
    logo = admin.find_logo()
    if logo:
        b64 = base64.b64encode(logo.read_bytes()).decode()
        mime = "image/svg+xml" if logo.suffix == ".svg" else "image/png"
        emblem = f'<img src="data:{mime};base64,{b64}" style="height:64px;border-radius:8px;background:white;padding:3px;">'
    else:
        emblem = '<div class="monogramme">MIN<br>PMEESA</div>'
    st.markdown(f"""
    <div class="entete">
      {emblem}
      <div>
        <h1>Assistant documentaire intelligent — MINPMEESA</h1>
        <p>Exploitation du patrimoine documentaire en appui à l'Annuaire statistique
        et au Rapport annuel de performance · Division des Études, des Projets et de la Prospective</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    # Bannière institutionnelle (photo / Journées nationales de la PME) si déposée.
    banniere = admin.find_asset("banniere")
    if banniere:
        st.image(str(banniere), use_container_width=True)


# --------------------------------------------------------------------------- #
#  Onglet 1 — Interroger
# --------------------------------------------------------------------------- #
def tab_interroger(engine, mode: Mode):
    st.subheader("Interroger le patrimoine documentaire")
    st.caption("Posez une question ; la réponse est composée de passages sourcés. "
               "Toute donnée chiffrée est reprise littéralement de sa source.")

    colq, colc = st.columns([4, 1])
    query = colq.text_input("Votre question", key="q_interroger",
                            placeholder="Ex. : Quel est le nombre de PME estimé en 2023 ?")
    config_name = colc.selectbox("Récupération", list(CONFIGS.keys()), index=3,
                                 help="Étage de récupération (défaut : hybride + reranking).")

    with st.expander("Filtres avancés (métadonnées)"):
        c1, c2 = st.columns(2)
        types = c1.multiselect("Type de document",
                               ["annuaire_statistique", "note_conjoncture",
                                "rapport_activite", "document"])
        years = c2.multiselect("Année", [2022, 2023, 2024, 2025])

    if st.button("🔎 Interroger", key="btn_interroger") and query.strip():
        base = Filter()
        if types:
            base.doc_types = set(types)
        if years:
            base.years = set(years)
        results = engine.retrieve(query, mode=mode, run=CONFIGS[config_name], base_filter=base)
        ans = engine.answerer.answer(query, results, mode=mode)

        if ans.refused:
            st.warning(ans.message)
            return

        st.markdown("#### Réponse")
        for s in ans.sentences:
            st.markdown(
                f'<div class="rep-card">{s.text}<br><span class="cite">{s.citation}</span></div>',
                unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Exactitude chiffrée", f"{ans.numeric_audit.accuracy:.0%}",
                  f"{ans.numeric_audit.supported}/{ans.numeric_audit.total} nombres sourcés")
        m2.metric("Fidélité", f"{ans.faithfulness.faithfulness:.0%}",
                  f"{ans.faithfulness.n_supported}/{ans.faithfulness.n_sentences} énoncés")
        m3.metric("Sources", str(len(ans.sources)))
        if ans.numeric_audit.unsupported:
            st.error("Nombres non sourcés retirés par le garde-fou : "
                     + ", ".join(ans.numeric_audit.unsupported))

        st.markdown("#### Passages sources")
        for b in ans.context:
            status = b.result.chunk.diffusion_status.value
            tag = "🔒 interne" if status == "interne" else "✅ publié"
            with st.expander(f"[{b.sid}] {b.citation} · {tag}"):
                st.write(b.text)


# --------------------------------------------------------------------------- #
#  Onglet 2 — Collecte pour l'Annuaire
# --------------------------------------------------------------------------- #
def tab_collecte(engine):
    st.subheader("Collecte pour l'Annuaire statistique")
    st.caption("Réunit, par rubrique, les constats et données chiffrées sourcés "
               "à transcrire dans l'Annuaire. Mode production (corpus complet).")

    rubrique = st.selectbox("Rubrique de l'Annuaire", list(collecte.RUBRIQUES.keys()))
    colb1, colb2 = st.columns([1, 1])
    go = colb1.button("📋 Collecter cette rubrique")
    go_all = colb2.button("📚 Collecter toutes les rubriques")

    findings = None
    if go:
        findings = collecte.collect_rubrique(engine, rubrique, mode=Mode.PRODUCTION)
    elif go_all:
        with st.spinner("Collecte de l'ensemble des rubriques…"):
            findings = collecte.collect_all(engine, mode=Mode.PRODUCTION)

    if findings is not None:
        if not findings:
            st.info("Aucun constat trouvé pour cette sélection.")
            return
        rows = [{"Rubrique": f.rubrique, "Constat": f.sentence,
                 "Données chiffrées": ", ".join(f.numbers), "Référence": f.citation}
                for f in findings]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        c1.download_button("⬇️ Exporter en CSV", collecte.findings_to_csv(findings),
                           file_name="fiche_collecte_annuaire.csv", mime="text/csv")
        c2.download_button("⬇️ Exporter en Markdown", collecte.findings_to_markdown(findings),
                           file_name="fiche_collecte_annuaire.md", mime="text/markdown")


# --------------------------------------------------------------------------- #
#  Onglet 3 — Mettre à jour la documentation
# --------------------------------------------------------------------------- #
def tab_admin():
    st.subheader("Mettre à jour la documentation")
    st.caption("Ajoutez, remplacez ou retirez des documents, puis reconstruisez "
               "l'index pour les rendre interrogeables.")

    st.markdown("##### Documents du corpus")
    rows = admin.list_documents()
    for r in rows:
        c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
        etat = "🔒 interne" if r.diffusion_status == "interne" else "✅ publié"
        manque = "" if r.exists else " ⚠️ fichier absent"
        c1.write(f"**{r.title}**{manque}")
        c2.write(r.doc_type)
        c3.write(f"{etat} · {r.year or ''} {r.quarter or ''}")
        if c4.button("🗑️", key=f"del_{r.doc_id}", help="Retirer ce document"):
            admin.delete_document(r.doc_id)
            reset_engine()
            st.success(f"Document « {r.title} » retiré. Pensez à reconstruire l'index.")
            st.rerun()

    st.divider()
    st.markdown("##### Ajouter / remplacer un document")
    with st.form("ajout_doc", clear_on_submit=True):
        pdf = st.file_uploader("Fichier PDF", type=["pdf"])
        c1, c2 = st.columns(2)
        title = c1.text_input("Titre du document")
        doc_type = c2.selectbox("Type", ["note_conjoncture", "annuaire_statistique",
                                         "rapport_activite", "document"])
        c3, c4, c5 = st.columns(3)
        statut = c3.selectbox("Statut de diffusion", ["publie", "interne"],
                              help="« interne » = document de travail, invisible en mode consultation.")
        year = c4.number_input("Année", min_value=2000, max_value=2100, value=2025, step=1)
        quarter = c5.selectbox("Trimestre (facultatif)", ["", "T1", "T2", "T3", "T4"])
        submit = st.form_submit_button("➕ Enregistrer le document")
        if submit:
            if not pdf or not title.strip():
                st.error("Veuillez fournir un fichier PDF et un titre.")
            else:
                doc_id = admin.add_or_update_document(
                    title=title.strip(), doc_type=doc_type, diffusion_status=statut,
                    year=int(year), quarter=quarter or None,
                    file_bytes=pdf.getvalue(), original_filename=pdf.name)
                reset_engine()
                st.success(f"Document enregistré (id : {doc_id}). "
                           f"Cliquez sur « Reconstruire l'index » pour l'activer.")

    st.divider()
    c1, c2 = st.columns([1, 2])
    if c1.button("🔧 Reconstruire l'index"):
        with st.spinner("Reconstruction de l'index…"):
            meta = admin.rebuild_index()
            reset_engine()
        st.success(f"Index reconstruit : {meta}")

    st.markdown("##### Images de l'application (logo, bannière, couverture)")
    st.caption("Déposez chaque image ; elle s'affiche après rechargement de la page.")
    for name, label in admin.ASSET_NAMES.items():
        current = admin.find_asset(name)
        cols = st.columns([3, 1])
        up = cols[0].file_uploader(label, type=["png", "jpg", "jpeg", "svg", "webp"],
                                   key=f"asset_{name}")
        if current:
            try:
                cols[1].image(str(current), width=90)
            except Exception:
                cols[1].caption("déposée ✓")
        if up is not None:
            ext = up.name.rsplit(".", 1)[-1]
            admin.save_asset(name, up.getvalue(), extension=ext)
            st.success(f"« {label} » enregistrée. Rechargez la page pour la voir.")


# --------------------------------------------------------------------------- #
#  Assemblage
# --------------------------------------------------------------------------- #
def main():
    inject_css()
    render_header()
    engine = load_engine()

    with st.sidebar:
        st.markdown("### Mode d'usage")
        mode_label = st.radio(
            "Profil d'utilisateur",
            ["🏭 Production (agents)", "🏛️ Consultation (décideurs)"],
            help="Production : corpus interne + publié. Consultation : publié uniquement.")
        mode = Mode.PRODUCTION if mode_label.startswith("🏭") else Mode.CONSULTATION
        couleur = VERT if mode == Mode.PRODUCTION else ROUGE
        st.markdown(f'<span class="badge-mode" style="background:{couleur}">'
                    f'{mode.value.upper()}</span>', unsafe_allow_html=True)
        if mode == Mode.CONSULTATION:
            st.info("🔒 Cloisonnement actif : les documents internes non validés "
                    "sont inaccessibles.")
        couverture = admin.find_asset("couverture")
        if couverture:
            st.divider()
            st.markdown("### Dernier Annuaire")
            st.image(str(couverture), use_container_width=True)
        st.divider()
        st.markdown("### Index")
        st.json(engine.store.meta, expanded=False)
        st.caption("Système RAG hybride · Mémoire M2 MDSMS · ISSEA-CEMAC")

    t1, t2, t3 = st.tabs(["🔎 Interroger", "📋 Collecte pour l'Annuaire",
                          "⚙️ Mettre à jour la documentation"])
    with t1:
        tab_interroger(engine, mode)
    with t2:
        tab_collecte(engine)
    with t3:
        tab_admin()


if __name__ == "__main__":
    main()
