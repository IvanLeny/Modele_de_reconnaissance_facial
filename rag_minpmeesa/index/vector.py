"""
Indexation vectorielle dense (chapitre 3.3).

Les passages sont encodés en vecteurs denses, L2-normalisés, puis comparés à la
requête par similarité cosinus (= produit scalaire après normalisation). Sur un
corpus de cette taille (quelques centaines à quelques milliers de passages), une
recherche exacte par produit matriciel NumPy est à la fois exacte et instantanée ;
un index approché (FAISS/HNSW) constitue un point d'extension documenté pour un
passage à l'échelle, sans changer l'interface.

La recherche sémantique récupère les passages proches par le sens même sans
recouvrement de termes — complément direct de BM25.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np

from ..config import EmbeddingConfig
from .embeddings import EmbeddingBackend, get_embedding_backend


class VectorIndex:
    def __init__(self, backend: EmbeddingBackend, cfg: EmbeddingConfig):
        self.backend = backend
        self.cfg = cfg
        self._matrix: np.ndarray | None = None

    def build(self, texts: List[str]) -> "VectorIndex":
        # Le substitut TF-IDF doit apprendre son vocabulaire sur le corpus.
        self.backend.fit(texts)
        self._matrix = self.backend.encode_documents(texts).astype(np.float32)
        return self

    def search(self, query: str, top_k: int) -> List[Tuple[int, float]]:
        if self._matrix is None:
            raise RuntimeError("Index vectoriel non construit.")
        q = self.backend.encode_queries([query]).astype(np.float32)[0]
        sims = self._matrix @ q
        top_k = min(top_k, len(sims))
        idx = np.argpartition(-sims, top_k - 1)[:top_k]
        idx = idx[np.argsort(-sims[idx])]
        return [(int(i), float(sims[i])) for i in idx]

    def save(self, path_matrix: Path, path_backend: Path) -> None:
        np.save(path_matrix, self._matrix)
        self.backend.save(path_backend)

    def load(self, path_matrix: Path, path_backend: Path) -> "VectorIndex":
        self._matrix = np.load(path_matrix)
        self.backend.load(path_backend)
        return self
