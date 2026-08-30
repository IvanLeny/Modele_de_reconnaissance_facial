"""
Indexation lexicale BM25 (chapitre 3.3).

BM25 (Okapi) est la référence de la recherche lexicale : il pondère les termes
par leur rareté (IDF) et sature la fréquence, ce qui convient à un corpus où les
requêtes des agents sont souvent des termes exacts (nom d'un tableau, d'une
région, d'un indicateur). Il capte les correspondances de surface que la
recherche sémantique manque parfois — d'où sa complémentarité avec le vectoriel.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from .text_utils import tokenize_fr


class LexicalIndex:
    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._n = 0

    def build(self, texts: List[str]) -> "LexicalIndex":
        corpus_tokens = [tokenize_fr(t) or ["<vide>"] for t in texts]
        self._bm25 = BM25Okapi(corpus_tokens)
        self._n = len(texts)
        return self

    def search(self, query: str, top_k: int) -> List[Tuple[int, float]]:
        """Renvoie [(index_du_passage, score_bm25)] triés par score décroissant."""
        if self._bm25 is None:
            raise RuntimeError("Index lexical non construit.")
        q = tokenize_fr(query) or ["<vide>"]
        scores = self._bm25.get_scores(q)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(i, float(scores[i])) for i in order[:top_k]]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "n": self._n}, f)

    def load(self, path: Path) -> "LexicalIndex":
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._bm25 = state["bm25"]
        self._n = state["n"]
        return self
