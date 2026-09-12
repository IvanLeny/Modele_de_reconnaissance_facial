"""
Études d'ablation (démarche §7).

Chacune répond à une question qu'un examinateur posera :
  1. constante de fusion k ∈ {1,5,10,20,60,100} ;
  2. dimension de la réduction sémantique hors-ligne ∈ {64,128,256,384} ;
  3. taille des segments et recouvrement (au moins trois configurations) ;
  4. expansion de requête activée / désactivée ;
  5. réordonnancement activé / désactivé, par catégorie de requête.

Les sorties sont au format de l'étape 6 (CSV « ; »), écrites dans
outputs/runs/ablations_<horodatage>/. Réindexation locale rapide (corpus réduit).
"""
from __future__ import annotations

import csv
import statistics as st
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..config import get_settings, Settings
from ..engine import RAGEngine
from ..ingestion import build_chunks
from ..index.store import IndexStore
from ..retrieval.pipeline import HybridRetriever, RetrievalConfigRun, CONFIGS
from .gold import load_gold, is_relevant
from .metrics import ndcg_at_k, mrr, precision_at_k, recall_at_k


def _rel_count(chunks, gold):
    return {q.id: sum(1 for c in chunks if is_relevant(c, q)) for q in gold}


def mean_metrics(engine: RAGEngine, run: RetrievalConfigRun, gold, relc) -> Dict[str, float]:
    acc = {k: [] for k in ["P@3", "P@5", "R@3", "R@5", "MRR", "nDCG@3", "nDCG@5"]}
    for q in gold:
        hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=10)
        rels = [is_relevant(h.chunk, q) for h in hits]
        tot = relc[q.id]
        acc["P@3"].append(precision_at_k(rels, 3))
        acc["P@5"].append(precision_at_k(rels, 5))
        acc["R@3"].append(recall_at_k(rels, 3, tot))
        acc["R@5"].append(recall_at_k(rels, 5, tot))
        acc["MRR"].append(mrr(rels))
        acc["nDCG@3"].append(ndcg_at_k(rels, 3, tot))
        acc["nDCG@5"].append(ndcg_at_k(rels, 5, tot))
    return {k: round(st.mean(v), 4) for k, v in acc.items()}


def _write(path: Path, rows: List[dict], fields: List[str]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def run_ablations(verbose: bool = True) -> Path:
    settings = get_settings()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = settings.paths.runs_dir / f"ablations_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    gold = load_gold()

    engine = RAGEngine().ensure_ready()
    relc = _rel_count(engine.store.chunks, gold)
    MFIELDS = ["P@3", "P@5", "R@3", "R@5", "MRR", "nDCG@3", "nDCG@5"]

    # -- 1. Balayage de la constante de fusion k ------------------------- #
    if verbose:
        print("  [7.1] balayage de k …")
    rows = []
    base_k = settings.retrieval.rrf_k
    for k in [1, 5, 10, 20, 60, 100]:
        settings.retrieval.rrf_k = k
        for code, run in [("C3", CONFIGS["hybride"]), ("C4", CONFIGS["hybride+rerank"])]:
            m = mean_metrics(engine, run, gold, relc)
            rows.append({"k": k, "configuration": code, **m})
    settings.retrieval.rrf_k = base_k
    _write(out / "ablation_k.csv", rows, ["k", "configuration"] + MFIELDS)

    # -- 4. Expansion de requête activée / désactivée -------------------- #
    if verbose:
        print("  [7.4] expansion on/off …")
    rows = []
    for exp in (True, False):
        for code, base in CONFIGS.items():
            run = RetrievalConfigRun(base.use_lexical, base.use_vector,
                                     base.use_reranker, base.label, use_expansion=exp)
            m = mean_metrics(engine, run, gold, relc)
            rows.append({"expansion": "on" if exp else "off", "configuration": code, **m})
    _write(out / "ablation_expansion.csv", rows,
           ["expansion", "configuration"] + MFIELDS)

    # -- 5. Réordonnancement on/off, par catégorie ----------------------- #
    if verbose:
        print("  [7.5] reranking par catégorie …")
    cats = sorted({q.category for q in gold})
    rows = []
    for cat in cats:
        gcat = [q for q in gold if q.category == cat]
        for code, run in [("C3 (sans rerank)", CONFIGS["hybride"]),
                          ("C4 (avec rerank)", CONFIGS["hybride+rerank"])]:
            m = mean_metrics(engine, run, gcat, relc)
            rows.append({"categorie": cat, "n": len(gcat), "configuration": code, **m})
    _write(out / "ablation_rerank_par_categorie.csv", rows,
           ["categorie", "n", "configuration"] + MFIELDS)

    # -- 2. Dimension de la réduction sémantique (réindexation) ---------- #
    if verbose:
        print("  [7.2] dimension SVD {64,128,256,384} (réindexation) …")
    rows = []
    base_dim = settings.embedding.tfidf_dims
    chunks = build_chunks(settings, verbose=False)
    for dim in [64, 128, 256, 384]:
        settings.embedding.tfidf_dims = dim
        store = IndexStore(settings).build(chunks, verbose=False)
        eng2 = RAGEngine(settings)
        eng2.store = store
        eng2.retriever = HybridRetriever(store, settings)
        relc2 = _rel_count(store.chunks, gold)
        for code, run in [("C2", CONFIGS["vectoriel"]), ("C3", CONFIGS["hybride"]),
                          ("C4", CONFIGS["hybride+rerank"])]:
            m = mean_metrics(eng2, run, gold, relc2)
            rows.append({"dim_demandee": dim, "dim_effective": store.meta["embedding_dim"],
                         "configuration": code, **m})
    settings.embedding.tfidf_dims = base_dim
    _write(out / "ablation_dim_svd.csv", rows,
           ["dim_demandee", "dim_effective", "configuration"] + MFIELDS)

    # -- 3. Taille des segments et recouvrement (réindexation) ----------- #
    if verbose:
        print("  [7.3] taille de segment / recouvrement (réindexation) …")
    rows = []
    base_sz, base_ov = settings.ingestion.chunk_size_words, settings.ingestion.chunk_overlap_words
    for size, overlap in [(120, 30), (180, 40), (260, 60)]:
        settings.ingestion.chunk_size_words = size
        settings.ingestion.chunk_overlap_words = overlap
        ck = build_chunks(settings, verbose=False)
        store = IndexStore(settings).build(ck, verbose=False)
        eng2 = RAGEngine(settings)
        eng2.store = store
        eng2.retriever = HybridRetriever(store, settings)
        relc2 = _rel_count(store.chunks, gold)
        for code, run in [("C4", CONFIGS["hybride+rerank"])]:
            m = mean_metrics(eng2, run, gold, relc2)
            rows.append({"taille": size, "recouvrement": overlap,
                         "n_passages": len(ck), "configuration": code, **m})
    settings.ingestion.chunk_size_words = base_sz
    settings.ingestion.chunk_overlap_words = base_ov
    _write(out / "ablation_segments.csv", rows,
           ["taille", "recouvrement", "n_passages", "configuration"] + MFIELDS)

    if verbose:
        print(f"  Ablations écrites dans {out}")
    return out


if __name__ == "__main__":
    run_ablations()
