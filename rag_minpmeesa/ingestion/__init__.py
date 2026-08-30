"""Ingestion : extraction, nettoyage, segmentation, métadonnées (chapitre 3.2)."""
from .registry import load_registry
from .extract import extract_document
from .clean import clean_text
from .chunk import chunk_document
from .pipeline import build_chunks

__all__ = [
    "load_registry",
    "extract_document",
    "clean_text",
    "chunk_document",
    "build_chunks",
]
