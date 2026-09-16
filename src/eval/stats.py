"""
Analyse statistique du harnais de génération (cahier des charges, Étape 9).

Ne se contente jamais de moyennes nues :
  - moyennes assorties de leur erreur-type ;
  - test des rangs signés de Wilcoxon apparié par indicateur (C1/C0, C2/C1,
    C3/C2, C1/baseline), avec décompte gagne/perd/égalité ;
  - ventilation par exercice ;
  - note de granularité : avec n indicateurs, tout écart < 1/n est du bruit ;
  - figures 300 dpi (barres groupées ; nuage exactitude × couverture, figure
    centrale de l'hypothèse H2).

Lit le `per_indicator.csv` et le `baseline_naive.csv` d'un run (dernier par
défaut) et écrit un rapport CSV + les figures dans outputs/figures/.
"""
from __future__ import annotations

import csv
import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _latest_run() -> Path:
    runs = sorted(Path("outputs/runs").glob("generation_*"))
    if not runs:
        raise FileNotFoundError("Aucun run de génération. Lancez src.eval.runner.")
    return runs[-1]


def _read(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _paired(rows: List[dict], ca: str, cb: str, metric: str) -> Tuple[List[float], List[float]]:
    """Vecteurs appariés (même indicateur, même exercice) pour deux configs."""
    idx = {}
    for r in rows:
        idx[(r["configuration"], r["code_indicateur"], r["exercice"])] = float(r[metric])
    a, b = [], []
    cles = {(r["code_indicateur"], r["exercice"]) for r in rows}
    for (code, ex) in sorted(cles):
        ka, kb = (ca, code, ex), (cb, code, ex)
        if ka in idx and kb in idx:
            a.append(idx[ka]); b.append(idx[kb])
    return a, b


def _wlt(a: List[float], b: List[float], eps: float = 1e-9) -> Tuple[int, int, int]:
    win = sum(1 for x, y in zip(a, b) if x - y > eps)
    lose = sum(1 for x, y in zip(a, b) if y - x > eps)
    return win, lose, len(a) - win - lose


def _wilcoxon(a: List[float], b: List[float]) -> Optional[float]:
    from scipy.stats import wilcoxon
    diffs = [x - y for x, y in zip(a, b)]
    if not diffs or all(abs(d) < 1e-12 for d in diffs):
        return None
    try:
        return round(float(wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")[1]), 4)
    except ValueError:
        return None


def _se(xs: List[float]) -> float:
    return round(st.pstdev(xs) / (len(xs) ** 0.5), 4) if len(xs) > 1 else 0.0


def run_stats(run_dir: Optional[str] = None, verbose: bool = True) -> Path:
    run = Path(run_dir) if run_dir else _latest_run()
    per = _read(run / "per_indicator.csv")
    baseline = _read(run / "baseline_naive.csv") if (run / "baseline_naive.csv").exists() else []
    configs = ["C0", "C1", "C2", "C3", "C4"]
    n = len({(r["code_indicateur"], r["exercice"]) for r in per})

    # Moyennes ± erreur-type par configuration (métrique primaire : rouge1).
    resume = []
    for c in configs:
        vals = [float(r["rouge1"]) for r in per if r["configuration"] == c]
        exa = [float(r["exactitude"]) for r in per if r["configuration"] == c]
        resume.append({"configuration": c, "rouge1_moyen": round(st.mean(vals), 4) if vals else 0,
                       "rouge1_se": _se(vals), "exactitude_moyenne": round(st.mean(exa), 4) if exa else 0})

    # Comparaisons appariées (Wilcoxon + win/lose/tie) sur rouge1.
    comps = []
    for ca, cb in [("C1", "C0"), ("C2", "C1"), ("C3", "C2")]:
        a, b = _paired(per, ca, cb, "rouge1")
        w, l, t = _wlt(a, b)
        comps.append({"comparaison": f"{ca} vs {cb}", "n": len(a),
                      "delta_moyen": round((st.mean(a) - st.mean(b)) if a else 0, 4),
                      "gagne": w, "perd": l, "egalite": t, "p_wilcoxon": _wilcoxon(a, b)})
    # C1 vs référence naïve.
    if baseline:
        bidx = {(r["code_indicateur"], r["exercice"]): float(r["rouge1"]) for r in baseline}
        a, b = [], []
        for r in per:
            if r["configuration"] == "C1":
                k = (r["code_indicateur"], r["exercice"])
                if k in bidx:
                    a.append(float(r["rouge1"])); b.append(bidx[k])
        if a:
            w, l, t = _wlt(a, b)
            comps.append({"comparaison": "C1 vs baseline_naïve", "n": len(a),
                          "delta_moyen": round(st.mean(a) - st.mean(b), 4),
                          "gagne": w, "perd": l, "egalite": t, "p_wilcoxon": _wilcoxon(a, b)})

    # Écriture du rapport.
    with open(run / "stats_generation.csv", "w", encoding="utf-8-sig", newline="") as f:
        f.write("# Moyennes par configuration (métrique primaire : ROUGE-1)\n")
        w = csv.DictWriter(f, fieldnames=["configuration", "rouge1_moyen", "rouge1_se",
                                          "exactitude_moyenne"], delimiter=";")
        w.writeheader(); w.writerows(resume)
        f.write(f"\n# Comparaisons appariées (Wilcoxon) — n={n}, granularité 1/n={1/n:.4f}\n")
        w2 = csv.DictWriter(f, fieldnames=["comparaison", "n", "delta_moyen",
                                           "gagne", "perd", "egalite", "p_wilcoxon"], delimiter=";")
        w2.writeheader(); w2.writerows(comps)

    _figures(per, resume, run)
    if verbose:
        print(f"  n = {n} indicateurs ; granularité 1/n = {1/n:.4f}")
        for c in comps:
            print(f"  {c['comparaison']:>22} : Δ={c['delta_moyen']:+.4f} "
                  f"(g/p/é {c['gagne']}/{c['perd']}/{c['egalite']}), p={c['p_wilcoxon']}")
        print(f"  Rapport + figures : {run}")
    return run


def _figures(per: List[dict], resume: List[dict], run: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figdir = Path("outputs/figures"); figdir.mkdir(parents=True, exist_ok=True)

    # Barres groupées : ROUGE-1 et exactitude par configuration.
    cfgs = [r["configuration"] for r in resume]
    r1 = [r["rouge1_moyen"] for r in resume]
    exa = [r["exactitude_moyenne"] for r in resume]
    x = range(len(cfgs))
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.bar([i - 0.2 for i in x], r1, 0.4, label="ROUGE-1", color="#1b7837")
    ax.bar([i + 0.2 for i in x], exa, 0.4, label="Exactitude numérique", color="#762a83")
    ax.set_xticks(list(x)); ax.set_xticklabels(cfgs)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Score moyen")
    ax.set_title("Qualité rédactionnelle et exactitude par configuration")
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(figdir / "figure_generation_configs.png", dpi=300); plt.close(fig)

    # Nuage exactitude × couverture (figure centrale H2).
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    couleurs = {"C0": "#b35806", "C1": "#f1a340", "C2": "#998ec3",
                "C3": "#1b7837", "C4": "#542788"}
    for c in ["C0", "C1", "C3", "C4"]:
        xs = [float(r["couverture"]) for r in per if r["configuration"] == c]
        ys = [float(r["exactitude"]) for r in per if r["configuration"] == c]
        if xs:
            ax.scatter(xs, ys, s=18, alpha=0.6, label=c, color=couleurs.get(c))
    ax.set_xlabel("Couverture des indicateurs"); ax.set_ylabel("Exactitude numérique")
    ax.set_xlim(-0.03, 1.03); ax.set_ylim(-0.03, 1.05)
    ax.set_title("Exactitude vs couverture (hypothèse H2)")
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(figdir / "figure_generation_exactitude_couverture.png", dpi=300); plt.close(fig)


if __name__ == "__main__":
    run_stats()
