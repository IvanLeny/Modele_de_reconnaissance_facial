"""
Harnais d'évaluation (cahier des charges, Étape 8).

Exécute les configurations C0–C4 et la référence naïve sur les indicateurs
évaluables, calcule les métriques, et écrit les cinq sorties obligatoires dans
outputs/runs/<horodatage>/. Reproductible (graine fixée) ; le régime d'exécution
(référence LLM vs dégradé extractif) est inscrit dans run_metadata.json.

Configurations :
  C0 génération sans référence documentaire (données + intitulé seulement) ;
  C1 C0 + commentaires homologues antérieurs ;
  C2 C1 + filtrage temporel strict et par métadonnées ;
  C3 C2 + contrôle de citation littérale et abstention (système complet) ;
  C4 restitution extractive (borne supérieure de fidélité).
"""
from __future__ import annotations

import csv
import json
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..ingestion.ingest import build_store, Referentiel
from ..retrieval.store import Store
from ..retrieval.context import assembler_contexte, Contexte
from ..generation.generate import generer
from ..guards.numeric import controler_propositions, Proposition
from ..guards.abstention import decider
from .metrics import rouge_n, rouge_l, similarite_lexicale, taux_soutenu, couverture


@dataclass
class Config:
    code: str
    prior_comments: bool
    guard: bool
    abstention: bool
    extractif_pur: bool = False


CONFIGS = [
    Config("C0", prior_comments=False, guard=False, abstention=False),
    Config("C1", prior_comments=True, guard=False, abstention=False),
    Config("C2", prior_comments=True, guard=False, abstention=False),   # + filtrage (toujours actif ici)
    Config("C3", prior_comments=True, guard=True, abstention=True),
    Config("C4", prior_comments=True, guard=False, abstention=False, extractif_pur=True),
]

MFIELDS = ["rouge1", "rouge2", "rougeL", "similarite", "taux_soutenu",
           "exactitude", "couverture", "n_propositions", "n_ecartees",
           "abstention", "latence_ms"]


def _contexte_config(store: Store, code: str, exercice: int, intitule: str,
                     cfg: Config) -> Contexte:
    ctx = assembler_contexte(store, code, exercice, intitule=intitule)
    if not cfg.prior_comments:
        ctx.commentaires_anterieurs = []      # C0 : aucune référence documentaire
    return ctx


def _evaluer_unite(store: Store, ref: Referentiel, exercice: int, code: str,
                   cfg: Config, seed: int) -> Dict:
    intitule = ref.intitule.get((exercice, code), "")
    reference = ref.reference.get((exercice, code), "")
    ctx = _contexte_config(store, code, exercice, intitule, cfg)

    # Abstention (C3) : décision AVANT génération.
    abst = False
    if cfg.abstention:
        d = decider(ctx.bloc_donnees(), ctx.commentaires_anterieurs,
                    min_confiance=0.25, tableau_apparie=bool(ctx.valeurs_n))
        abst = d.abstention

    t0 = time.perf_counter()
    if abst:
        props: List[Proposition] = []
        texte = ""
        exactitude = 1.0
        n_ecartees = 0
    else:
        res = generer(ctx, intitule, seed=seed)
        props = res.propositions
        if cfg.guard:
            audit = controler_propositions(props, ctx.bloc_donnees())
            props = [a.proposition for a in audit.retenues]
            n_ecartees = len(audit.ecartees)
            exactitude = audit.exactitude
        else:
            audit = controler_propositions(props, ctx.bloc_donnees())
            n_ecartees = 0
            exactitude = audit.exactitude
        texte = " ".join(p.texte for p in props)
    latence = (time.perf_counter() - t0) * 1000.0

    prop_txts = [p.texte for p in props]
    return {
        "code_indicateur": code, "exercice": exercice, "configuration": cfg.code,
        "rouge1": rouge_n(texte, reference, 1), "rouge2": rouge_n(texte, reference, 2),
        "rougeL": rouge_l(texte, reference),
        "similarite": similarite_lexicale(texte, reference),
        "taux_soutenu": taux_soutenu(prop_txts, ctx.rendu()),
        "exactitude": exactitude,
        "couverture": couverture(len(prop_txts), max(1, len(ctx.valeurs_n))),
        "n_propositions": len(prop_txts), "n_ecartees": n_ecartees,
        "abstention": int(abst), "latence_ms": round(latence, 1),
        "_texte": texte,
    }


def _baseline_naive(ref: Referentiel) -> List[Dict]:
    """Commentaire publié de l'exercice précédent comparé à celui de l'exercice
    évalué : ce qu'un agent obtiendrait sans outil. Le système doit faire mieux."""
    rows = []
    for (exercice, code), reference in ref.reference.items():
        anterieur = ref.reference.get((exercice - 1, code))
        if not anterieur:
            continue
        rows.append({
            "code_indicateur": code, "exercice": exercice,
            "rouge1": rouge_n(anterieur, reference, 1),
            "rougeL": rouge_l(anterieur, reference),
            "similarite": similarite_lexicale(anterieur, reference),
        })
    return rows


def _mean(rows: List[Dict], key: str) -> float:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def run_evaluation(corpus_dir: str = "data/corpus", seed: int = 42,
                   verbose: bool = True) -> Path:
    store, ref = build_store(corpus_dir, verbose=verbose)
    unites = sorted(ref.reference.keys())
    if verbose:
        print(f"  {len(unites)} unités évaluables (exercice, indicateur).")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("outputs/runs") / f"generation_{ts}"
    (out / "textes_produits").mkdir(parents=True, exist_ok=True)

    per_rows: List[Dict] = []
    for cfg in CONFIGS:
        for (exercice, code) in unites:
            r = _evaluer_unite(store, ref, exercice, code, cfg, seed)
            texte = r.pop("_texte")
            per_rows.append(r)
            (out / "textes_produits" / f"{cfg.code}_{exercice}_{code[:40]}.txt").write_text(
                f"[{cfg.code}] exercice {exercice} — {code}\n"
                f"RÉFÉRENCE:\n{ref.reference[(exercice, code)][:800]}\n\n"
                f"PRODUIT:\n{texte}\n", encoding="utf-8")

    # per_indicator.csv
    with open(out / "per_indicator.csv", "w", encoding="utf-8-sig", newline="") as f:
        cols = ["code_indicateur", "exercice", "configuration"] + MFIELDS
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(per_rows)

    # metrics_global.csv (moyenne par configuration)
    with open(out / "metrics_global.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["configuration"] + MFIELDS, delimiter=";")
        w.writeheader()
        for cfg in CONFIGS:
            sub = [r for r in per_rows if r["configuration"] == cfg.code]
            w.writerow({"configuration": cfg.code, **{m: _mean(sub, m) for m in MFIELDS}})

    # baseline_naive.csv
    base = _baseline_naive(ref)
    with open(out / "baseline_naive.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code_indicateur", "exercice", "rouge1",
                                          "rougeL", "similarite"], delimiter=";")
        w.writeheader()
        w.writerows(base)

    # run_metadata.json
    regime = generer(assembler_contexte(store, unites[0][1], unites[0][0],
                     intitule=ref.intitule[unites[0]]), ref.intitule[unites[0]]).regime \
        if unites else "n/a"
    meta = {
        "horodatage": ts, "graine": seed, "regime": regime,
        "n_unites": len(unites), "configurations": [c.code for c in CONFIGS],
        "python": sys.version.split()[0], "plateforme": platform.platform(),
        "note": "Régime dégradé (extractif) si aucun LLM local n'est configuré ; "
                "les écarts C0/C1/C2 ne se révèlent pleinement qu'en régime de "
                "référence (Ollama).",
    }
    (out / "run_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    if verbose:
        print(f"  Régime : {regime}")
        print(f"  Sorties écrites dans {out}")
    return out


if __name__ == "__main__":
    run_evaluation()
