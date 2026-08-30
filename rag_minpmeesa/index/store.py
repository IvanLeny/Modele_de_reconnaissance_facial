"""
Magasin d'index (chapitre 3.3) : construit, persiste et recharge l'ensemble
{passages + index lexical + index vectoriel + métadonnées de construction}.

La persistance rend les expériences du chapitre 4 reproductibles : on construit
l'index une fois, puis toutes les configurations comparées partagent exactement
le même corpus indexé.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..config import Settings, get_settings
from ..schema import Chunk
from .embeddings import get_embedding_backend
from .lexical import LexicalIndex
from .vector import VectorIndex


class IndexStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.chunks: List[Chunk] = []
        self.lexical: LexicalIndex | None = None
        self.vector: VectorIndex | None = None
        self.meta: dict = {}

    # ---- construction ---------------------------------------------------- #
    def build(self, chunks: List[Chunk], verbose: bool = True) -> "IndexStore":
        self.chunks = chunks
        texts = [c.text for c in chunks]

        if verbose:
            print("  [index] construction de l'index lexical (BM25)…")
        self.lexical = LexicalIndex().build(texts)

        if verbose:
            print("  [index] construction de l'index vectoriel…")
        backend = get_embedding_backend(self.settings.embedding, verbose=verbose)
        self.vector = VectorIndex(backend, self.settings.embedding).build(texts)

        self.meta = {
            "n_chunks": len(chunks),
            "embedding_backend": backend.name,
            "embedding_dim": backend.dim,
            "n_documents": len({c.doc_id for c in chunks}),
        }
        if verbose:
            print(f"  [index] terminé : {self.meta}")
        return self

    # ---- persistance ----------------------------------------------------- #
    def save(self) -> None:
        d = self.settings.paths.index_dir
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "chunks.jsonl", "w", encoding="utf-8") as f:
            for c in self.chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        self.lexical.save(d / "lexical.pkl")
        self.vector.save(d / "vector_matrix.npy", d / "vector_backend.pkl")
        with open(d / "index_meta.json", "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)

    def load(self) -> "IndexStore":
        d = self.settings.paths.index_dir
        self.chunks = []
        with open(d / "chunks.jsonl", encoding="utf-8") as f:
            for line in f:
                self.chunks.append(Chunk.from_dict(json.loads(line)))
        self.lexical = LexicalIndex().load(d / "lexical.pkl")
        backend = get_embedding_backend(self.settings.embedding, verbose=False)
        self.vector = VectorIndex(backend, self.settings.embedding).load(
            d / "vector_matrix.npy", d / "vector_backend.pkl")
        with open(d / "index_meta.json", encoding="utf-8") as f:
            self.meta = json.load(f)
        return self

    def exists(self) -> bool:
        d = self.settings.paths.index_dir
        return (d / "chunks.jsonl").exists() and (d / "vector_matrix.npy").exists()
