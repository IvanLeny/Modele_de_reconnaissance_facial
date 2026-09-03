"""
Export détaillé de l'évaluation (chapitre 4) — sorties brutes par question.

Régénère, à partir de l'index déjà construit :
  1. eval_per_question.csv     : identifiant, catégorie (CU1-CU5), mode, vérité de
     terrain (document/pages), nombre de passages pertinents, référence ;
  2. eval_runs_top10.csv       : pour C1 à C4, les 10 premiers segments récupérés,
     avec rang, identifiant, document, pages, score et pertinence ;
  3. eval_ndcg5_per_question.csv : nDCG@5 par question et par configuration
     (pour le test apparié sur les différences) ;
  4. eval_channel_correlation.csv : par question, le tau de Kendall entre les
     scores BM25 (C1) et vectoriels (C2) sur le corpus autorisé, et le
     recouvrement des top-5 entre C1 et C2 ;
  5. eval_by_category.csv      : métriques moyennes ventilées par catégorie ;
  6. eval_details.json         : l'ensemble sous forme structurée.

Usage :  python scripts/export_eval_details.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import statistics as st
from pathlib import Path

# Rend le paquet importable quel que soit le dossier d'exécution.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scipy.stats import kendalltau

from rag_minpmeesa.engine import RAGEngine
from rag_minpmeesa.config import get_settings
from rag_minpmeesa.retrieval.pipeline import CONFIGS
from rag_minpmeesa.retrieval.filters import mode_filter
from rag_minpmeesa.evaluation.gold import load_gold, is_relevant
from rag_minpmeesa.evaluation.metrics import ndcg_at_k, mrr, precision_at_k, recall_at_k

CONFIG_LABELS = {"lexical": "C1", "vectoriel": "C2",
                 "hybride": "C3", "hybride+rerank": "C4"}
SCORE_TYPE = {"lexical": "BM25", "vectoriel": "cosinus",
              "hybride": "RRF", "hybride+rerank": "rerang_mélangé"}


def channel_score(cfg_name, r):
    if cfg_name == "lexical":
        return r.score_lexical
    if cfg_name == "vectoriel":
        return r.score_vector
    return r.score


def main():
    settings = get_settings()
    out = settings.paths.results_dir
    out.mkdir(parents=True, exist_ok=True)
    eng = RAGEngine().ensure_ready()
    gold = load_gold()
    chunks = eng.store.chunks

    # passages pertinents présents dans l'index (dénominateur des métriques)
    rel_count = {q.id: sum(1 for c in chunks if is_relevant(c, q)) for q in gold}

    per_question, runs_rows, ndcg_rows, corr_rows = [], [], [], []
    details = {}
    by_cat = {}

    for q in gold:
        gold_dp = "; ".join(f"{r['doc_id']} p.{'/'.join(map(str, r['pages']))}"
                            for r in q.relevant)
        per_question.append({
            "qid": q.id, "categorie": q.category, "mode": q.mode.value,
            "question": q.question, "verite_terrain": gold_dp,
            "n_passages_pertinents": rel_count[q.id],
            "internal_only": q.internal_only, "reference": q.reference,
        })
        qd = {"question": q.question, "categorie": q.category, "mode": q.mode.value,
              "verite_terrain": q.relevant, "n_passages_pertinents": rel_count[q.id],
              "configs": {}}
        ndcg_row = {"qid": q.id, "categorie": q.category}

        # --- C1..C4 : top-10 + métriques par question ---
        for name, run in CONFIGS.items():
            lab = CONFIG_LABELS[name]
            hits = eng.retrieve(q.question, mode=q.mode, run=run, top_k=10)
            rels = [is_relevant(h.chunk, q) for h in hits]
            ndcg_row[lab] = round(ndcg_at_k(rels, 5, rel_count[q.id]), 4)
            seg = []
            for rank, h in enumerate(hits, 1):
                sc = channel_score(name, h)
                row = {
                    "qid": q.id, "categorie": q.category, "config": lab,
                    "rang": rank, "chunk_id": h.chunk.chunk_id,
                    "doc_id": h.chunk.doc_id,
                    "pages": f"{h.chunk.page_start}-{h.chunk.page_end}",
                    "score": round(float(sc), 6) if sc is not None else "",
                    "type_score": SCORE_TYPE[name],
                    "pertinent": int(is_relevant(h.chunk, q)),
                }
                runs_rows.append(row)
                seg.append(row)
            qd["configs"][lab] = {
                "ndcg@5": ndcg_row[lab],
                "mrr": round(mrr(rels), 4),
                "p@3": round(precision_at_k(rels, 3), 4),
                "p@5": round(precision_at_k(rels, 5), 4),
                "recall@5": round(recall_at_k(rels, 5, rel_count[q.id]), 4),
                "top10": seg,
            }
        ndcg_rows.append(ndcg_row)

        # --- corrélation des canaux C1 vs C2 (sur le corpus autorisé) ---
        flt = mode_filter(q.mode)
        allowed = sorted(flt.allowed_indices(chunks))
        n = len(chunks)
        lex = dict(eng.store.lexical.search(q.question, n))
        vec = dict(eng.store.vector.search(q.question, n))
        bm = [lex.get(i, 0.0) for i in allowed]
        co = [vec.get(i, 0.0) for i in allowed]
        tau, _ = kendalltau(bm, co)
        allowed_set = set(allowed)
        top5_c1 = [i for i, _ in sorted(((i, s) for i, s in lex.items() if i in allowed_set),
                                        key=lambda kv: kv[1], reverse=True)][:5]
        top5_c2 = [i for i, _ in sorted(((i, s) for i, s in vec.items() if i in allowed_set),
                                        key=lambda kv: kv[1], reverse=True)][:5]
        overlap = len(set(top5_c1) & set(top5_c2))
        corr_rows.append({"qid": q.id, "categorie": q.category,
                          "kendall_tau_C1_C2": round(float(tau), 4),
                          "recouvrement_top5_C1_C2": overlap})
        qd["kendall_tau_C1_C2"] = round(float(tau), 4)
        qd["recouvrement_top5_C1_C2"] = overlap

        details[q.id] = qd
        by_cat.setdefault(q.category, []).append((q.id, ndcg_row, overlap, tau, rel_count[q.id]))

    # --- ventilation par catégorie ---
    cat_rows = []
    for cat, items in sorted(by_cat.items()):
        cat_rows.append({
            "categorie": cat, "n_questions": len(items),
            "n_pertinents_moyen": round(st.mean(x[4] for x in items), 2),
            "nDCG@5_C1": round(st.mean(x[1]["C1"] for x in items), 4),
            "nDCG@5_C2": round(st.mean(x[1]["C2"] for x in items), 4),
            "nDCG@5_C3": round(st.mean(x[1]["C3"] for x in items), 4),
            "nDCG@5_C4": round(st.mean(x[1]["C4"] for x in items), 4),
            "recouvrement_top5_moyen": round(st.mean(x[2] for x in items), 2),
            "kendall_tau_moyen": round(st.mean(x[3] for x in items), 4),
        })

    # --- écriture des fichiers ---
    def write_csv(name, rows, fields):
        with open(out / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            w.writeheader()
            w.writerows(rows)

    write_csv("eval_per_question.csv", per_question,
              ["qid", "categorie", "mode", "question", "verite_terrain",
               "n_passages_pertinents", "internal_only", "reference"])
    write_csv("eval_runs_top10.csv", runs_rows,
              ["qid", "categorie", "config", "rang", "chunk_id", "doc_id",
               "pages", "score", "type_score", "pertinent"])
    write_csv("eval_ndcg5_per_question.csv", ndcg_rows,
              ["qid", "categorie", "C1", "C2", "C3", "C4"])
    write_csv("eval_channel_correlation.csv", corr_rows,
              ["qid", "categorie", "kendall_tau_C1_C2", "recouvrement_top5_C1_C2"])
    write_csv("eval_by_category.csv", cat_rows,
              ["categorie", "n_questions", "n_pertinents_moyen",
               "nDCG@5_C1", "nDCG@5_C2", "nDCG@5_C3", "nDCG@5_C4",
               "recouvrement_top5_moyen", "kendall_tau_moyen"])
    with open(out / "eval_details.json", "w", encoding="utf-8") as f:
        json.dump({"corpus": eng.store.meta, "questions": details,
                   "par_categorie": cat_rows}, f, ensure_ascii=False, indent=2)

    # --- synthèse à l'écran ---
    mean_rel = st.mean(rel_count.values())
    mean_tau = st.mean(r["kendall_tau_C1_C2"] for r in corr_rows)
    mean_ov = st.mean(r["recouvrement_top5_C1_C2"] for r in corr_rows)
    print(f"Questions : {len(gold)} | passages pertinents/question (moyenne) : {mean_rel:.2f}")
    print(f"Corrélation des canaux C1/C2 : tau de Kendall moyen = {mean_tau:.3f} ; "
          f"recouvrement top-5 moyen = {mean_ov:.2f}/5")
    print(f"Fichiers écrits dans {out} :")
    for n in ["eval_per_question.csv", "eval_runs_top10.csv",
              "eval_ndcg5_per_question.csv", "eval_channel_correlation.csv",
              "eval_by_category.csv", "eval_details.json"]:
        print("  -", n)


if __name__ == "__main__":
    main()
