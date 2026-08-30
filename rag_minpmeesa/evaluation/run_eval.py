"""
Protocole d'évaluation complet (chapitre 4) — exécutable.

Produit :
  1. Étude d'ablation de la RÉCUPÉRATION (4.2) : lexical, vectoriel, hybride,
     hybride+reranking, avec nDCG@5, MRR, Precision@3, Recall@5.
  2. Évaluation de la RESTITUTION (4.3) : fidélité et exactitude chiffrée de la
     réponse ancrée, et taux de citation correcte de la source de référence.
  3. Test de CLOISONNEMENT (4.4) : sur les questions dont la réponse n'existe que
     dans un document interne, on vérifie qu'aucune fuite ne se produit en mode
     consultation (taux de fuite attendu : 0).
  4. VALIDATION DES HYPOTHÈSES (4.6) au regard des seuils fixés a priori (A.3).

Les résultats sont enregistrés en JSON et en Markdown dans data/results/.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from typing import Dict, List

from ..config import Mode, get_settings
from ..engine import RAGEngine
from ..retrieval.pipeline import CONFIGS
from .gold import load_gold, is_relevant, GoldQuestion
from .metrics import ndcg_at_k, mrr, precision_at_k, recall_at_k
from ..generation.numeric import audit_numbers


EVAL_TOP_K = 10


# --------------------------------------------------------------------------- #
#  1. Récupération
# --------------------------------------------------------------------------- #
def _relevant_chunk_counts(engine: RAGEngine, gold: List[GoldQuestion]) -> Dict[str, int]:
    """Nombre de passages pertinents PRÉSENTS dans l'index pour chaque question.

    La pertinence est annotée au niveau (document, page) mais l'unité récupérée
    est le passage : le dénominateur des métriques doit donc compter les passages
    de l'index qui recoupent une page de référence — sans quoi rappel et nDCG
    peuvent dépasser 1.
    """
    counts = {}
    for q in gold:
        counts[q.id] = sum(1 for c in engine.store.chunks if is_relevant(c, q))
    return counts


def evaluate_retrieval(engine: RAGEngine, gold: List[GoldQuestion]) -> Dict[str, dict]:
    rel_counts = _relevant_chunk_counts(engine, gold)
    results: Dict[str, dict] = {}
    for name, run in CONFIGS.items():
        per_q = {"ndcg@5": [], "mrr": [], "p@3": [], "recall@5": []}
        for q in gold:
            total_rel = rel_counts[q.id]
            hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=EVAL_TOP_K)
            rels = [is_relevant(h.chunk, q) for h in hits]
            per_q["ndcg@5"].append(ndcg_at_k(rels, 5, total_rel))
            per_q["mrr"].append(mrr(rels))
            per_q["p@3"].append(precision_at_k(rels, 3))
            per_q["recall@5"].append(recall_at_k(rels, 5, total_rel))
        results[name] = {m: round(statistics.mean(v), 4) for m, v in per_q.items()}
    return results


# --------------------------------------------------------------------------- #
#  2. Restitution (fidélité, exactitude chiffrée, citation correcte)
# --------------------------------------------------------------------------- #
def evaluate_generation(engine: RAGEngine, gold: List[GoldQuestion]) -> dict:
    faith_vals, numacc_vals, cite_ok, refusals = [], [], [], 0
    gold_number_recall = []
    details = []
    for q in gold:
        ans = engine.query(q.question, mode=q.mode)
        if ans.refused:
            refusals += 1
            details.append({"id": q.id, "refused": True})
            continue
        faith_vals.append(ans.faithfulness.faithfulness)
        numacc_vals.append(ans.numeric_audit.accuracy)
        # citation correcte : au moins une source citée provient du bon document
        gold_docs = {r["doc_id"] for r in q.relevant}
        cited_docs = {b.result.chunk.doc_id for b in ans.context}
        cite_ok.append(bool(gold_docs & cited_docs))
        # rappel des données chiffrées de référence effectivement restituées
        if q.gold_numbers:
            audit = audit_numbers(" ".join(q.gold_numbers), [ans.summary])
            gold_number_recall.append(audit.accuracy)
        details.append({
            "id": q.id,
            "faithfulness": round(ans.faithfulness.faithfulness, 3),
            "numeric_accuracy": round(ans.numeric_audit.accuracy, 3),
            "cite_ok": bool(gold_docs & cited_docs),
        })
    return {
        "faithfulness_moyenne": round(statistics.mean(faith_vals), 4) if faith_vals else 0.0,
        "exactitude_chiffree_moyenne": round(statistics.mean(numacc_vals), 4) if numacc_vals else 0.0,
        "taux_citation_correcte": round(statistics.mean([1.0 if c else 0.0 for c in cite_ok]), 4) if cite_ok else 0.0,
        "rappel_donnees_gold": round(statistics.mean(gold_number_recall), 4) if gold_number_recall else None,
        "refus": refusals,
        "details": details,
    }


# --------------------------------------------------------------------------- #
#  3. Cloisonnement des modes (sécurité)
# --------------------------------------------------------------------------- #
def evaluate_cloisonnement(engine: RAGEngine, gold: List[GoldQuestion]) -> dict:
    internal_qs = [q for q in gold if q.internal_only]
    leaks = 0
    accessible_prod = 0
    details = []
    for q in internal_qs:
        internal_docs = {r["doc_id"] for r in q.relevant}
        # Mode consultation : ne doit JAMAIS renvoyer le document interne.
        cons = engine.retrieve(q.question, mode=Mode.CONSULTATION, top_k=EVAL_TOP_K)
        leaked = {h.chunk.doc_id for h in cons} & internal_docs
        # Mode production : doit pouvoir y accéder.
        prod = engine.retrieve(q.question, mode=Mode.PRODUCTION, top_k=EVAL_TOP_K)
        reachable = bool({h.chunk.doc_id for h in prod} & internal_docs)
        if leaked:
            leaks += 1
        if reachable:
            accessible_prod += 1
        details.append({"id": q.id, "fuite_consultation": bool(leaked),
                        "accessible_production": reachable})
    n = len(internal_qs)
    return {
        "n_questions_internes": n,
        "taux_fuite_consultation": round(leaks / n, 4) if n else 0.0,
        "taux_acces_production": round(accessible_prod / n, 4) if n else 0.0,
        "details": details,
    }


# --------------------------------------------------------------------------- #
#  4. Validation des hypothèses
# --------------------------------------------------------------------------- #
def validate_hypotheses(retrieval: dict, generation: dict, cloison: dict) -> dict:
    s = get_settings().thresholds
    out = {}

    # H1 : hybride > meilleure config simple (nDCG@5 et MRR)
    best_simple_ndcg = max(retrieval["lexical"]["ndcg@5"], retrieval["vectoriel"]["ndcg@5"])
    best_simple_mrr = max(retrieval["lexical"]["mrr"], retrieval["vectoriel"]["mrr"])
    g_ndcg = retrieval["hybride"]["ndcg@5"] - best_simple_ndcg
    g_mrr = retrieval["hybride"]["mrr"] - best_simple_mrr
    out["H1"] = {
        "gain_ndcg@5": round(g_ndcg, 4), "gain_mrr": round(g_mrr, 4),
        "seuils": {"ndcg": s.h1_min_ndcg_gain, "mrr": s.h1_min_mrr_gain},
        "validee": g_ndcg >= s.h1_min_ndcg_gain and g_mrr >= s.h1_min_mrr_gain,
    }

    # H2 : hybride+rerank > hybride (nDCG@5 et Precision@3)
    g2_ndcg = retrieval["hybride+rerank"]["ndcg@5"] - retrieval["hybride"]["ndcg@5"]
    g2_p3 = retrieval["hybride+rerank"]["p@3"] - retrieval["hybride"]["p@3"]
    out["H2"] = {
        "gain_ndcg@5": round(g2_ndcg, 4), "gain_p@3": round(g2_p3, 4),
        "seuils": {"ndcg": s.h2_min_ndcg_gain, "precision": s.h2_min_precision_gain},
        "validee": g2_ndcg >= s.h2_min_ndcg_gain and g2_p3 >= s.h2_min_precision_gain,
    }

    # H3 : ancrage documentaire (fidélité et exactitude chiffrée mesurables ici)
    out["H3"] = {
        "faithfulness": generation["faithfulness_moyenne"],
        "exactitude_chiffree": generation["exactitude_chiffree_moyenne"],
        "seuils": {"faithfulness": s.h3_min_faithfulness,
                   "exactitude": s.h3_min_numeric_accuracy},
        "validee": (generation["faithfulness_moyenne"] >= s.h3_min_faithfulness
                    and generation["exactitude_chiffree_moyenne"] >= s.h3_min_numeric_accuracy),
        "note": "La réduction du taux d'énoncés non soutenus vs 'sans récupération' "
                "requiert un baseline génératif (mode LLM local) ; les critères de "
                "fidélité et d'exactitude chiffrée de l'ancrage sont validés ici.",
    }

    # Cloisonnement (support de H0 / prémisse de sécurité des deux modes)
    out["cloisonnement"] = {
        "taux_fuite_consultation": cloison["taux_fuite_consultation"],
        "validee": cloison["taux_fuite_consultation"] == 0.0,
    }

    # H4 / H5 : protocole terrain (temps) — non exécutable hors ministère.
    out["H4_H5"] = {
        "validee": None,
        "note": "Hypothèses de gain de temps : protocole contrôlé auprès d'agents "
                "et de décideurs (chap. 2.6). Non exécutable dans l'environnement "
                "logiciel ; critères fixés a priori au Tableau A.3.",
    }
    return out


# --------------------------------------------------------------------------- #
#  Orchestration + rapport
# --------------------------------------------------------------------------- #
def run_full_evaluation(engine: RAGEngine | None = None, verbose: bool = True) -> dict:
    settings = get_settings()
    engine = engine or RAGEngine().ensure_ready()
    gold = load_gold()

    if verbose:
        print(f"  Jeu de test : {len(gold)} questions.")
        print("  [4.2] Évaluation de la récupération (ablation)…")
    retrieval = evaluate_retrieval(engine, gold)
    if verbose:
        print("  [4.3] Évaluation de la restitution ancrée…")
    generation = evaluate_generation(engine, gold)
    if verbose:
        print("  [4.4] Test de cloisonnement des modes…")
    cloison = evaluate_cloisonnement(engine, gold)
    if verbose:
        print("  [4.6] Validation des hypothèses…")
    hypotheses = validate_hypotheses(retrieval, generation, cloison)

    embedding_backend = engine.store.meta.get("embedding_backend", "?")
    reranker_name = engine.retriever.reranker.name
    surrogate = ("tfidf" in embedding_backend) or ("feature" in reranker_name)

    report = {
        "n_questions": len(gold),
        "index_meta": engine.store.meta,
        "embedding_backend": embedding_backend,
        "reranker": reranker_name,
        "config_surrogate_offline": surrogate,
        "retrieval": retrieval,
        "generation": generation,
        "cloisonnement": cloison,
        "hypotheses": hypotheses,
    }

    settings.paths.results_dir.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.results_dir / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    md = render_markdown(report)
    with open(settings.paths.results_dir / "evaluation.md", "w", encoding="utf-8") as f:
        f.write(md)
    if verbose:
        print(md)
        print(f"\n  Résultats enregistrés dans {settings.paths.results_dir}")
    return report


def render_markdown(r: dict) -> str:
    lines = []
    lines.append("# Résultats de l'évaluation — système RAG hybride MINPMEESA\n")
    lines.append(f"- Jeu de test : **{r['n_questions']} questions** annotées.")
    lines.append(f"- Encodeur vectoriel : `{r.get('embedding_backend','?')}`")
    lines.append(f"- Réordonnanceur : `{r.get('reranker','?')}`")
    lines.append(f"- Index : {r['index_meta']}\n")
    if r.get("config_surrogate_offline"):
        lines.append(
            "> **Configuration hors-ligne (substituts).** Cet environnement d'exécution "
            "n'a pas d'accès réseau aux modèles pré-entraînés : les résultats ci-dessous "
            "sont produits avec le substitut vectoriel TF-IDF/LSA et/ou le réordonnanceur "
            "à traits. La **configuration de référence** — encodeur de phrases multilingue "
            "et cross-encodeur exécutés localement — est attendue au-dessus de ces valeurs, "
            "notamment sur la complémentarité hybride (H1) et l'apport du reranking (H2). "
            "Le protocole et les seuils restent identiques ; seuls les modèles changent.\n")

    lines.append("## 4.2 Récupération (étude d'ablation)\n")
    lines.append("| Configuration | nDCG@5 | MRR | Precision@3 | Recall@5 |")
    lines.append("|---|---|---|---|---|")
    order = ["lexical", "vectoriel", "hybride", "hybride+rerank"]
    for name in order:
        m = r["retrieval"][name]
        lines.append(f"| {name} | {m['ndcg@5']:.3f} | {m['mrr']:.3f} "
                     f"| {m['p@3']:.3f} | {m['recall@5']:.3f} |")

    g = r["generation"]
    lines.append("\n## 4.3 Restitution ancrée dans les sources\n")
    lines.append(f"- Fidélité moyenne (énoncés soutenus) : **{g['faithfulness_moyenne']:.3f}**")
    lines.append(f"- Exactitude chiffrée moyenne (nombres sourcés) : **{g['exactitude_chiffree_moyenne']:.3f}**")
    lines.append(f"- Taux de citation correcte du document de référence : **{g['taux_citation_correcte']:.3f}**")
    if g.get("rappel_donnees_gold") is not None:
        lines.append(f"- Rappel des données chiffrées de référence : **{g['rappel_donnees_gold']:.3f}**")
    lines.append(f"- Refus (aucune source pertinente) : {g['refus']}")

    c = r["cloisonnement"]
    lines.append("\n## 4.4 Cloisonnement des modes (sécurité)\n")
    lines.append(f"- Questions à information interne : {c['n_questions_internes']}")
    lines.append(f"- Taux de fuite en mode consultation : **{c['taux_fuite_consultation']:.3f}** "
                 f"(attendu : 0)")
    lines.append(f"- Taux d'accès en mode production : **{c['taux_acces_production']:.3f}**")

    lines.append("\n## 4.6 Validation des hypothèses (seuils a priori, Tableau A.3)\n")
    h = r["hypotheses"]
    def verdict(v):
        return "✅ validée" if v is True else ("❌ non validée" if v is False else "⏳ protocole terrain")
    lines.append(f"- **H1** (fusion hybride) : gain nDCG@5 = {h['H1']['gain_ndcg@5']:+.3f}, "
                 f"gain MRR = {h['H1']['gain_mrr']:+.3f} → {verdict(h['H1']['validee'])}")
    lines.append(f"- **H2** (reranking) : gain nDCG@5 = {h['H2']['gain_ndcg@5']:+.3f}, "
                 f"gain P@3 = {h['H2']['gain_p@3']:+.3f} → {verdict(h['H2']['validee'])}")
    lines.append(f"- **H3** (ancrage) : fidélité = {h['H3']['faithfulness']:.3f}, "
                 f"exactitude chiffrée = {h['H3']['exactitude_chiffree']:.3f} → {verdict(h['H3']['validee'])}")
    lines.append(f"- **Cloisonnement** : fuite = {h['cloisonnement']['taux_fuite_consultation']:.3f} "
                 f"→ {verdict(h['cloisonnement']['validee'])}")
    lines.append(f"- **H4/H5** (gain de temps) : {verdict(h['H4_H5']['validee'])} — {h['H4_H5']['note']}")
    lines.append(f"\n> H3 — {h['H3']['note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    run_full_evaluation()
