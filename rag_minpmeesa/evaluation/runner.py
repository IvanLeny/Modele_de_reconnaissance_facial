"""
Harnais d'évaluation (démarche §6) — exécution des configurations C0 à C5.

Tout passe par ce harnais, en ligne de commande, reproductible : l'interface
n'intervient jamais dans les résultats. Pour chaque configuration, il calcule les
métriques de récupération et de restitution, sépare la latence de récupération du
reste de la chaîne, et écrit dans outputs/runs/<horodatage>/ :

    metrics_global.csv   une ligne par configuration
    runs_top10.csv       question, config, rang, passage, score, pertinence
    per_question.csv     métriques détaillées par question et par configuration
    restitution.csv      réponses générées et audit des garde-fous (C0, C5)
    run_metadata.json    régime, modèles, paramètres, graines, versions, horodatage

Régime d'exécution :
  - « référence » si l'encodeur neuronal (et le cross-encodeur) sont chargés ;
  - « hors-ligne » si le système a basculé sur les substituts.
Les configurations génératives C0 et C5 requièrent un modèle de langage local :
en son absence, C0 n'est pas exécutée et C5 utilise la restitution extractive
ancrée (les garde-fous s'appliquent). Le régime est consigné dans run_metadata.
"""
from __future__ import annotations

import csv
import json
import platform
import statistics as st
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..config import get_settings, Mode
from ..engine import RAGEngine
from ..retrieval.pipeline import RetrievalConfigRun
from .gold import load_gold, is_relevant
from .metrics import ndcg_at_k, mrr, precision_at_k, recall_at_k
from ..generation.numeric import audit_numbers
from ..generation.guardrails import faithfulness_report


# Configurations du protocole (démarche §6). C0/C5 sont génératives.
RUN_CONFIGS = {
    "C1": RetrievalConfigRun(True, False, False, "lexicale seule"),
    "C2": RetrievalConfigRun(False, True, False, "sémantique seule"),
    "C3": RetrievalConfigRun(True, True, False, "fusion hybride"),
    "C4": RetrievalConfigRun(True, True, True, "hybride+métadonnées+rerank"),
}
C5_RETRIEVAL = RUN_CONFIGS["C4"]   # C5 = C4 + génération ancrée avec garde-fous


def _peak_rss_mo() -> float:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return 0.0


def _lib_versions() -> dict:
    v = {"python": platform.python_version()}
    for m in ("numpy", "sklearn", "rank_bm25", "pymupdf", "scipy"):
        try:
            v[m] = __import__(m).__version__
        except Exception:
            v[m] = "n/a"
    return v


def run_evaluation(engine: RAGEngine | None = None, verbose: bool = True) -> Path:
    settings = get_settings()
    engine = engine or RAGEngine().ensure_ready()
    gold = load_gold()
    chunks = engine.store.chunks

    # Régime et disponibilité du modèle génératif.
    backend = engine.store.meta.get("embedding_backend", "?")
    regime = "hors-ligne" if "tfidf" in backend else "référence"
    llm_ready = bool(settings.generation.llm_base_url and settings.generation.llm_model)

    # Dénominateur des métriques : passages pertinents présents dans l'index.
    rel_count = {q.id: sum(1 for c in chunks if is_relevant(c, q)) for q in gold}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = settings.paths.runs_dir / ts
    out.mkdir(parents=True, exist_ok=True)

    runs_rows: List[dict] = []
    perq_rows: List[dict] = []
    resti_rows: List[dict] = []
    global_rows: List[dict] = []

    # --- Configurations de récupération C1..C4 --------------------------- #
    def eval_retrieval(code: str, run: RetrievalConfigRun):
        acc = {m: [] for m in ["p3", "p5", "r3", "r5", "mrr", "n3", "n5", "lat"]}
        for q in gold:
            t0 = time.perf_counter()
            hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=10)
            lat = (time.perf_counter() - t0) * 1000.0
            rels = [is_relevant(h.chunk, q) for h in hits]
            tot = rel_count[q.id]
            first = next((i + 1 for i, r in enumerate(rels) if r), 0)
            m = {
                "p3": precision_at_k(rels, 3), "p5": precision_at_k(rels, 5),
                "r3": recall_at_k(rels, 3, tot), "r5": recall_at_k(rels, 5, tot),
                "mrr": mrr(rels), "n3": ndcg_at_k(rels, 3, tot),
                "n5": ndcg_at_k(rels, 5, tot), "lat": lat,
            }
            for k, v in m.items():
                acc[k].append(v)
            perq_rows.append({
                "question_id": q.id, "categorie": q.category, "configuration": code,
                "nb_pertinents": tot, "rang_premier_pertinent": first,
                "P@3": round(m["p3"], 4), "P@5": round(m["p5"], 4),
                "R@3": round(m["r3"], 4), "R@5": round(m["r5"], 4),
                "MRR": round(m["mrr"], 4), "nDCG@3": round(m["n3"], 4),
                "nDCG@5": round(m["n5"], 4), "latence_ms": round(lat, 1),
            })
            for rang, h in enumerate(hits, 1):
                sc = (h.score_lexical if run.label.startswith("lex")
                      else h.score_vector if run.label.startswith("sém")
                      else h.score)
                runs_rows.append({
                    "question_id": q.id, "configuration": code, "rang": rang,
                    "passage_id": h.chunk.chunk_id, "score": round(float(sc or 0.0), 6),
                    "pertinent": int(is_relevant(h.chunk, q)),
                })
        return acc

    for code, run in RUN_CONFIGS.items():
        if verbose:
            print(f"  [{code}] {run.label} …")
        acc = eval_retrieval(code, run)
        global_rows.append({
            "configuration": code, "libelle": run.label,
            "P@3": round(st.mean(acc["p3"]), 4), "P@5": round(st.mean(acc["p5"]), 4),
            "R@3": round(st.mean(acc["r3"]), 4), "R@5": round(st.mean(acc["r5"]), 4),
            "MRR": round(st.mean(acc["mrr"]), 4), "nDCG@3": round(st.mean(acc["n3"]), 4),
            "nDCG@5": round(st.mean(acc["n5"]), 4),
            "fidelite": "", "exactitude_num": "", "taux_citation": "", "taux_abstention": "",
            "latence_recup_med_ms": round(st.median(acc["lat"]), 1),
            "latence_recup_max_ms": round(max(acc["lat"]), 1),
            "latence_totale_med_ms": round(st.median(acc["lat"]), 1),
            "latence_totale_max_ms": round(max(acc["lat"]), 1),
        })

    # --- C5 : C4 + restitution ancrée avec garde-fous -------------------- #
    if verbose:
        print("  [C5] génération ancrée + garde-fous …")
    fid, exa, cit, absten = [], [], [], []
    lat_ret, lat_tot = [], []
    for q in gold:
        t0 = time.perf_counter()
        hits = engine.retrieve(q.question, mode=q.mode, run=C5_RETRIEVAL, top_k=10)
        tr = (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        ans = engine.answerer.answer(q.question, hits[:settings.retrieval.top_k_final], mode=q.mode)
        tg = (time.perf_counter() - t1) * 1000.0
        lat_ret.append(tr)
        lat_tot.append(tr + tg)
        refused = int(ans.refused)
        absten.append(refused)
        if not ans.refused:
            fid.append(ans.faithfulness.faithfulness)
            exa.append(ans.numeric_audit.accuracy)
            cit.append(1.0 if ans.sources else 0.0)
        resti_rows.append({
            "question_id": q.id, "configuration": "C5",
            "reponse": (ans.summary or ans.message)[:1000],
            "nb_enonces": ans.faithfulness.n_sentences if not ans.refused else 0,
            "nb_enonces_soutenus": ans.faithfulness.n_supported if not ans.refused else 0,
            "valeurs_extraites": ans.numeric_audit.total if not ans.refused else 0,
            "valeurs_appariees": ans.numeric_audit.supported if not ans.refused else 0,
            "valeurs_ecartees": len(ans.numeric_audit.unsupported) if not ans.refused else 0,
            "abstention": refused,
        })
        # per_question pour C5 reprend la récupération de C4 (mêmes passages).
        rels = [is_relevant(h.chunk, q) for h in hits]
        tot = rel_count[q.id]
        perq_rows.append({
            "question_id": q.id, "categorie": q.category, "configuration": "C5",
            "nb_pertinents": tot,
            "rang_premier_pertinent": next((i + 1 for i, r in enumerate(rels) if r), 0),
            "P@3": round(precision_at_k(rels, 3), 4), "P@5": round(precision_at_k(rels, 5), 4),
            "R@3": round(recall_at_k(rels, 3, tot), 4), "R@5": round(recall_at_k(rels, 5, tot), 4),
            "MRR": round(mrr(rels), 4), "nDCG@3": round(ndcg_at_k(rels, 3, tot), 4),
            "nDCG@5": round(ndcg_at_k(rels, 5, tot), 4), "latence_ms": round(tr + tg, 1),
        })
    global_rows.append({
        "configuration": "C5", "libelle": "C4 + génération ancrée (garde-fous)",
        "P@3": "", "P@5": "", "R@3": "", "R@5": "", "MRR": "", "nDCG@3": "", "nDCG@5": "",
        "fidelite": round(st.mean(fid), 4) if fid else "",
        "exactitude_num": round(st.mean(exa), 4) if exa else "",
        "taux_citation": round(st.mean(cit), 4) if cit else "",
        "taux_abstention": round(st.mean(absten), 4),
        "latence_recup_med_ms": round(st.median(lat_ret), 1),
        "latence_recup_max_ms": round(max(lat_ret), 1),
        "latence_totale_med_ms": round(st.median(lat_tot), 1),
        "latence_totale_max_ms": round(max(lat_tot), 1),
    })

    # --- C0 : génération sans récupération (référence basse) ------------- #
    c0_note = "non exécutée (régime hors-ligne : modèle de langage local requis)"
    if llm_ready:
        c0_note = "exécutée avec le modèle de langage local"
        for q in gold:
            ans = engine.answerer.answer(q.question, [], mode=q.mode)  # contexte vide
            resti_rows.append({
                "question_id": q.id, "configuration": "C0",
                "reponse": (ans.summary or ans.message)[:1000],
                "nb_enonces": ans.faithfulness.n_sentences if ans.faithfulness else 0,
                "nb_enonces_soutenus": ans.faithfulness.n_supported if ans.faithfulness else 0,
                "valeurs_extraites": ans.numeric_audit.total if ans.numeric_audit else 0,
                "valeurs_appariees": ans.numeric_audit.supported if ans.numeric_audit else 0,
                "valeurs_ecartees": len(ans.numeric_audit.unsupported) if ans.numeric_audit else 0,
                "abstention": int(ans.refused),
            })

    # --- Écriture des fichiers ------------------------------------------ #
    def write(name, rows, fields):
        with open(out / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            w.writeheader()
            w.writerows(rows)

    write("metrics_global.csv", global_rows,
          ["configuration", "libelle", "P@3", "P@5", "R@3", "R@5", "MRR",
           "nDCG@3", "nDCG@5", "fidelite", "exactitude_num", "taux_citation",
           "taux_abstention", "latence_recup_med_ms", "latence_recup_max_ms",
           "latence_totale_med_ms", "latence_totale_max_ms"])
    write("runs_top10.csv", runs_rows,
          ["question_id", "configuration", "rang", "passage_id", "score", "pertinent"])
    write("per_question.csv", perq_rows,
          ["question_id", "categorie", "configuration", "nb_pertinents",
           "rang_premier_pertinent", "P@3", "P@5", "R@3", "R@5", "MRR",
           "nDCG@3", "nDCG@5", "latence_ms"])
    write("restitution.csv", resti_rows,
          ["question_id", "configuration", "reponse", "nb_enonces",
           "nb_enonces_soutenus", "valeurs_extraites", "valeurs_appariees",
           "valeurs_ecartees", "abstention"])

    meta = {
        "horodatage": ts,
        "regime": regime,
        "modele_encodeur": settings.embedding.transformer_model if regime == "référence" else backend,
        "modele_reordonnanceur": engine.retriever.reranker.name,
        "modele_langage": f"{settings.generation.llm_model}@{settings.generation.llm_base_url}" if llm_ready else "aucun",
        "C0": c0_note,
        "C5_restitution": "extractive ancrée" if not llm_ready else "génération LLM ancrée",
        "n_questions": len(gold),
        "n_passages": len(chunks),
        "empreinte_memoire_mo": round(_peak_rss_mo(), 1),
        "graine": settings.seed,
        "parametres": settings.to_dict(),
        "versions": _lib_versions(),
    }
    (out / "run_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"\n  Régime : {regime} | C0 : {c0_note}")
        print(f"  Sorties écrites dans {out}")
    return out


if __name__ == "__main__":
    run_evaluation()
