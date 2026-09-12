"""
Figures d'évaluation 300 dpi (démarche §9).

Deux figures que le chapitre 4 appelle explicitement :
  1. courbe de balayage de la constante de fusion k (nDCG@5 selon k) ;
  2. courbe de calibration de l'abstention (sensibilité du refus et spécificité
     de la réponse selon le seuil, plus la distribution des confiances).

Rendu hors-ligne (backend Agg), libellés en français, 300 dpi, dans
outputs/figures/. Recalcule les données à partir du moteur pour rester
reproductible sans dépendre d'un CSV antérieur.
"""
from __future__ import annotations

import statistics as st
from pathlib import Path
from typing import List

from ..config import Mode, get_settings
from ..engine import RAGEngine
from ..retrieval.pipeline import CONFIGS
from .gold import load_gold, is_relevant
from .metrics import ndcg_at_k
from .calibration import _confidence, _load_out_of_scope, _decision_quality


def _use_agg():
    import matplotlib
    matplotlib.use("Agg")


def _ndcg5_for_k(engine, gold, relc, k: int, config_key: str) -> float:
    settings = get_settings()
    base = settings.retrieval.rrf_k
    settings.retrieval.rrf_k = k
    run = CONFIGS[config_key]
    vals = []
    for q in gold:
        hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=10)
        rels = [is_relevant(h.chunk, q) for h in hits]
        vals.append(ndcg_at_k(rels, 5, relc[q.id]))
    settings.retrieval.rrf_k = base
    return st.mean(vals)


def figure_balayage_k(engine, gold, relc, out_dir: Path) -> Path:
    import matplotlib.pyplot as plt
    ks = [1, 5, 10, 20, 60, 100]
    c3 = [_ndcg5_for_k(engine, gold, relc, k, "hybride") for k in ks]
    c4 = [_ndcg5_for_k(engine, gold, relc, k, "hybride+rerank") for k in ks]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(ks, c3, "o-", label="C3 — hybride", color="#1b7837")
    ax.plot(ks, c4, "s-", label="C4 — hybride + réordonnancement", color="#762a83")
    ax.axvline(60, color="grey", ls="--", lw=1, label="valeur conventionnelle k = 60")
    ax.set_xscale("log")
    ax.set_xticks(ks)
    ax.get_xaxis().set_major_formatter(plt.matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Constante de fusion k (RRF)")
    ax.set_ylabel("nDCG@5 moyen")
    ax.set_title("Sensibilité de la fusion à la constante k")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "figure_balayage_k.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def figure_calibration_abstention(engine, gold, out_dir: Path) -> Path:
    import matplotlib.pyplot as plt
    settings = get_settings()
    run = CONFIGS["hybride+rerank"]

    in_scope = [_confidence(engine.retrieve(q.question, mode=q.mode, run=run, top_k=5))
                for q in gold]
    oos_path = settings.paths.gold_dir / "hors_perimetre.json"
    out_scope = [_confidence(engine.retrieve(question, mode=Mode.PRODUCTION, run=run, top_k=5))
                 for question in _load_out_of_scope(oos_path)]

    lo = min(in_scope + out_scope)
    hi = max(in_scope + out_scope)
    grid = [lo + (hi - lo) * i / 60 for i in range(61)]
    q = [_decision_quality(t, in_scope, out_scope) for t in grid]
    sens = [r["sensibilite_refus"] for r in q]
    spec = [r["specificite_reponse"] for r in q]
    seuil = settings.abstention.min_lexical_score

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.2))

    # Panneau gauche : distributions des confiances.
    ax1.hist(in_scope, bins=10, alpha=0.6, color="#1b7837", label="en périmètre")
    ax1.hist(out_scope, bins=10, alpha=0.6, color="#b35806", label="hors périmètre")
    ax1.axvline(seuil, color="black", ls="--", lw=1.2, label=f"seuil = {seuil:g}")
    ax1.set_xlabel("Confiance lexicale (meilleur BM25)")
    ax1.set_ylabel("Nombre de requêtes")
    ax1.set_title("Séparation des populations")
    ax1.legend(fontsize=8)

    # Panneau droit : sensibilité / spécificité selon le seuil.
    ax2.plot(grid, sens, "-", color="#b35806", label="sensibilité du refus (hors périmètre)")
    ax2.plot(grid, spec, "-", color="#1b7837", label="spécificité (réponses gardées)")
    ax2.axvline(seuil, color="black", ls="--", lw=1.2, label=f"seuil = {seuil:g}")
    ax2.set_xlabel("Seuil de confiance")
    ax2.set_ylabel("Taux")
    ax2.set_ylim(-0.03, 1.03)
    ax2.set_title("Qualité de la décision d'abstention")
    ax2.legend(fontsize=8)

    fig.suptitle("Calibration du seuil d'abstention", fontsize=11)
    fig.tight_layout()
    path = out_dir / "figure_calibration_abstention.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def run_figures(verbose: bool = True) -> Path:
    _use_agg()
    settings = get_settings()
    out_dir = settings.paths.figures_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = RAGEngine().ensure_ready()
    gold = load_gold()
    relc = {q.id: sum(1 for c in engine.store.chunks if is_relevant(c, q)) for q in gold}

    p1 = figure_balayage_k(engine, gold, relc, out_dir)
    p2 = figure_calibration_abstention(engine, gold, out_dir)
    if verbose:
        print(f"  {p1}")
        print(f"  {p2}")
        print(f"  Figures écrites dans {out_dir}")
    return out_dir


if __name__ == "__main__":
    run_figures()
