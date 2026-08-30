"""Indexation lexicale et vectorielle (chapitre 3.3)."""
from .text_utils import normalize, tokenize_fr
from .embeddings import get_embedding_backend, EmbeddingBackend
from .lexical import LexicalIndex
from .vector import VectorIndex
from .store import IndexStore

__all__ = [
    "normalize",
    "tokenize_fr",
    "get_embedding_backend",
    "EmbeddingBackend",
    "LexicalIndex",
    "VectorIndex",
    "IndexStore",
]
