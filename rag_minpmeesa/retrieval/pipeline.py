"""
Chaîne de récupération hybride (chapitre 3.4) — orchestration.

Étapes :
    requête + mode
      -> filtrage (cloisonnement + métadonnées)
      -> canal lexical (BM25)      \\
      -> canal vectoriel (dense)    >  fusion RRF  -> reranking -> top-k final
                                    /
Chaque configuration comparée au chapitre 4 (lexical seul, vectoriel seul,
hybride, hybride+reranking) est un simple paramétrage de `RetrievalConfigRun`,
exécuté sur le MÊME index — garantissant une comparaison toutes choses égales.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..config import Mode, Settings, get_settings
from ..schema import Chunk, RetrievalResult
from ..index.store import IndexStore
from .filters import Filter, mode_filter
from .fusion import reciprocal_rank_fusion
from .rerank import Reranker, get_reranker


@dataclass
class RetrievalConfigRun:
    """Décrit une configuration de récupération (pour l'étude d'ablation)."""
    use_lexical: bool = True
    use_vector: bool = True
    use_reranker: bool = True
    label: str = "hybride+rerank"

    @property
    def is_hybrid(self) -> bool:
        return self.use_lexical and self.use_vector


# Configurations de référence du chapitre 4 (étude d'ablation).
CONFIGS = {
    "lexical": RetrievalConfigRun(True, False, False, "lexical"),
    "vectoriel": RetrievalConfigRun(False, True, False, "vectoriel"),
    "hybride": RetrievalConfigRun(True, True, False, "hybride"),
    "hybride+rerank": RetrievalConfigRun(True, True, True, "hybride+rerank"),
}


class HybridRetriever:
    def __init__(self, store: IndexStore, settings: Settings | None = None,
                 reranker: Optional[Reranker] = None, verbose: bool = False):
        self.store = store
        self.settings = settings or get_settings()
        self._reranker = reranker
        self._verbose = verbose

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = get_reranker(
                self.settings.retrieval,
                corpus_texts=[c.text for c in self.store.chunks],
                verbose=self._verbose,
            )
        return self._reranker

    def retrieve(
        self,
        query: str,
        mode: Mode = Mode.PRODUCTION,
        run: Optional[RetrievalConfigRun] = None,
        base_filter: Optional[Filter] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        cfg = self.settings.retrieval
        run = run or CONFIGS["hybride+rerank"]
        top_k = top_k or cfg.top_k_final
        chunks = self.store.chunks

        # 1) Filtrage : cloisonnement du mode + critères de recherche éventuels.
        flt = mode_filter(mode, base_filter)
        allowed = flt.allowed_indices(chunks)
        if not allowed:
            return []

        # Sur-échantillonnage puis restriction aux passages autorisés.
        over = max(60, cfg.top_k_lexical * 4, cfg.top_k_vector * 4)
        over = min(over, len(chunks))

        ranked_lists = {}
        if run.use_lexical:
            lex = [(i, s) for i, s in self.store.lexical.search(query, over) if i in allowed]
            lex = lex[:cfg.top_k_lexical]
            ranked_lists["lexical"] = lex
        if run.use_vector:
            vec = [(i, s) for i, s in self.store.vector.search(query, over) if i in allowed]
            vec = vec[:cfg.top_k_vector]
            ranked_lists["vector"] = vec

        # 2) Fusion des classements.
        if len(ranked_lists) == 1:
            # Configuration à un seul canal : le classement est directement celui du canal.
            (channel, ranked), = ranked_lists.items()
            fused = {idx: {"rrf": 1.0 / (1 + rank), "ranks": {channel: rank + 1},
                           "scores": {channel: raw}}
                     for rank, (idx, raw) in enumerate(ranked)}
        else:
            fused = reciprocal_rank_fusion(ranked_lists, k=cfg.rrf_k)

        # Ordre après fusion.
        fused_order = sorted(fused.items(), key=lambda kv: kv[1]["rrf"], reverse=True)
        candidates = fused_order[: cfg.top_k_fused]

        # 3) Construction des résultats.
        results: List[RetrievalResult] = []
        for idx, info in candidates:
            c = chunks[idx]
            results.append(RetrievalResult(
                chunk=c,
                score=info["rrf"],
                rank_lexical=info["ranks"].get("lexical"),
                rank_vector=info["ranks"].get("vector"),
                score_lexical=info["scores"].get("lexical"),
                score_vector=info["scores"].get("vector"),
                provenance="fusion" if len(ranked_lists) > 1 else list(ranked_lists)[0],
            ))

        # 4) Reranking éventuel des candidats fusionnés.
        #    Le classement final mélange le score de reranking et le prior de
        #    fusion (min-max normalisés), ce qui évite qu'un reranking imparfait
        #    ne dégrade le rappel du premier étage (cf. config.rerank_blend).
        if run.use_reranker and results:
            rr_scores = self.reranker.score(query, [r.chunk for r in results])
            fusion_scores = [r.score for r in results]

            def _minmax(xs):
                lo, hi = min(xs), max(xs)
                if hi - lo < 1e-12:
                    return [0.5 for _ in xs]
                return [(x - lo) / (hi - lo) for x in xs]

            rr_norm = _minmax(rr_scores)
            fu_norm = _minmax(fusion_scores)
            w = cfg.rerank_blend
            for r, s, rn, fn in zip(results, rr_scores, rr_norm, fu_norm):
                r.score_rerank = float(s)
                r.score = w * rn + (1 - w) * fn      # score de classement final
                r.provenance = "rerank"
            results.sort(key=lambda r: r.score, reverse=True)

        return results[:top_k]
