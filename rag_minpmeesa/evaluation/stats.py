"""
Statistiques inférentielles sur les configurations de récupération (démarche §9).

Complète le harnais (§6, moyennes) par les tests qu'un jury attend :
  - test de Wilcoxon apparié (signé) entre configurations, sur les nDCG@5
    par question, avec décompte gains / pertes / égalités (win/lose/tie) ;
  - tau de Kendall entre les classements de deux configurations (concordance
    de l'ordre des questions) ;
  - ventilation des métriques par catégorie de cas d'usage (CU1–CU5) ;
  - note de granularité : avec n questions et une pertinence annotée à la page,
    la plus petite variation détectable sur une métrique moyenne est de l'ordre
    de 1/(3n) — les écarts inférieurs ne sont pas interprétables.

Le test de Wilcoxon (non paramétrique, apparié) est adapté : petit échantillon,
mêmes questions évaluées sous chaque configuration, pas d'hypothèse de normalité.

Sortie : outputs/runs/stats_<horodatage>/ (CSV « ; » + résumé JSON).
"""
from __future__ import annotations

import csv
import json
import statistics as st
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

from ..engine import RAGEngine
from ..retrieval.pipeline import CONFIGS, RetrievalConfigRun
from .gold import load_gold, is_relevant
from .metrics import ndcg_at_k, mrr, precision_at_k, recall_at_k

# Ordre de présentation des configurations comparées.
CONFIG_ORDER = [("C1", "lexical"), ("C2", "vectoriel"),
                ("C3", "hybride"), ("C4", "hybride+rerank")]
PRIMARY = "nDCG@5"


def _per_question(engine: RAGEngine, gold, relc) -> Dict[str, Dict[str, List[float]]]:
    """Renvoie, par code de configuration, le vecteur des métriques par question
    (ordre des questions stable)."""
    out: Dict[str, Dict[str, List[float]]] = {}
    for code, key in CONFIG_ORDER:
        run = CONFIGS[key]
        acc = {m: [] for m in ["P@3", "P@5", "R@5", "MRR", "nDCG@3", "nDCG@5"]}
        for q in gold:
            hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=10)
            rels = [is_relevant(h.chunk, q) for h in hits]
            tot = relc[q.id]
            acc["P@3"].append(precision_at_k(rels, 3))
            acc["P@5"].append(precision_at_k(rels, 5))
            acc["R@5"].append(recall_at_k(rels, 5, tot))
            acc["MRR"].append(mrr(rels))
            acc["nDCG@3"].append(ndcg_at_k(rels, 3, tot))
            acc["nDCG@5"].append(ndcg_at_k(rels, 5, tot))
        out[code] = acc
    return out


def _win_lose_tie(a: List[float], b: List[float], eps: float = 1e-9) -> Tuple[int, int, int]:
    win = sum(1 for x, y in zip(a, b) if x - y > eps)
    lose = sum(1 for x, y in zip(a, b) if y - x > eps)
    tie = len(a) - win - lose
    return win, lose, tie


def _wilcoxon(a: List[float], b: List[float]) -> Tuple[float, float]:
    """Statistique et p-valeur du test de Wilcoxon apparié ; (nan, 1.0) si tous
    les écarts sont nuls (test non défini)."""
    from scipy.stats import wilcoxon
    diffs = [x - y for x, y in zip(a, b)]
    if all(abs(d) < 1e-12 for d in diffs):
        return float("nan"), 1.0
    try:
        stat, p = wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        return float(stat), float(p)
    except ValueError:
        return float("nan"), 1.0


def _kendall(a: List[float], b: List[float]) -> float:
    from scipy.stats import kendalltau
    tau, _ = kendalltau(a, b)
    return float(tau) if tau == tau else 0.0        # nan -> 0


def run_stats(verbose: bool = True) -> Path:
    from ..config import get_settings
    settings = get_settings()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = settings.paths.runs_dir / f"stats_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    engine = RAGEngine().ensure_ready()
    gold = load_gold()
    n = len(gold)
    relc = {q.id: sum(1 for c in engine.store.chunks if is_relevant(c, q)) for q in gold}
    pq = _per_question(engine, gold, relc)

    # -- 1. Comparaisons appariées (Wilcoxon + win/lose/tie) sur nDCG@5 ------ #
    codes = [c for c, _ in CONFIG_ORDER]
    cmp_rows = []
    for ca, cb in combinations(codes, 2):
        a, b = pq[ca][PRIMARY], pq[cb][PRIMARY]
        win, lose, tie = _win_lose_tie(a, b)
        stat, p = _wilcoxon(a, b)
        cmp_rows.append({
            "comparaison": f"{ca} vs {cb}",
            "metrique": PRIMARY,
            "moyenne_A": round(st.mean(a), 4),
            "moyenne_B": round(st.mean(b), 4),
            "delta_moyen": round(st.mean(a) - st.mean(b), 4),
            "gains_A": win, "pertes_A": lose, "egalites": tie,
            "wilcoxon_stat": round(stat, 4) if stat == stat else "n.d.",
            "p_valeur": round(p, 4),
            "kendall_tau": round(_kendall(a, b), 4),
        })
    _write(out / "stats_comparaisons.csv", cmp_rows, list(cmp_rows[0].keys()))

    # -- 2. Ventilation par catégorie de cas d'usage ------------------------ #
    cats = sorted({q.category for q in gold})
    cat_rows = []
    idx_by_cat = {cat: [i for i, q in enumerate(gold) if q.category == cat] for cat in cats}
    for cat in cats:
        idxs = idx_by_cat[cat]
        for code, _ in CONFIG_ORDER:
            vals = [pq[code][PRIMARY][i] for i in idxs]
            cat_rows.append({
                "categorie": cat, "n": len(idxs), "configuration": code,
                "nDCG@5_moyen": round(st.mean(vals), 4) if vals else 0.0,
                "P@5_moyen": round(st.mean([pq[code]["P@5"][i] for i in idxs]), 4) if vals else 0.0,
            })
    _write(out / "stats_par_categorie.csv", cat_rows, list(cat_rows[0].keys()))

    # -- 3. Résumé + note de granularité ------------------------------------ #
    granularite = 1.0 / (3 * n)
    summary = {
        "n_questions": n,
        "metrique_primaire": PRIMARY,
        "moyennes": {c: round(st.mean(pq[c][PRIMARY]), 4) for c in codes},
        "note_granularite": {
            "resolution_estimee": round(granularite, 4),
            "explication": (
                f"Avec n={n} questions et une pertinence annotée à la page (≈3 "
                f"passages pertinents par question), la plus petite variation "
                f"interprétable sur une moyenne est de l'ordre de 1/(3n) ≈ "
                f"{granularite:.4f}. Les écarts inférieurs relèvent du bruit "
                f"d'échantillonnage et ne sont pas commentés."),
        },
        "comparaison_cle": next(
            (r for r in cmp_rows if r["comparaison"] == "C3 vs C4"), None),
    }
    (out / "stats_resume.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"  n = {n} questions ; granularité ≈ {granularite:.4f}")
        for r in cmp_rows:
            print(f"  {r['comparaison']:>18} : Δ={r['delta_moyen']:+.4f} "
                  f"(g/p/é {r['gains_A']}/{r['pertes_A']}/{r['egalites']}), "
                  f"p={r['p_valeur']}, τ={r['kendall_tau']}")
        print(f"  Statistiques écrites dans {out}")
    return out


def _write(path: Path, rows: List[dict], fields: List[str]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    run_stats()
