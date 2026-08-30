"""
Orchestration de l'ingestion (chapitre 3.2) : corpus -> liste de passages.
"""
from __future__ import annotations

from typing import Dict, List

from ..config import Settings, get_settings
from ..schema import Chunk, DocumentMeta
from .registry import load_registry
from .extract import extract_document
from .clean import clean_text
from .chunk import chunk_document


def build_chunks(settings: Settings | None = None, verbose: bool = True) -> List[Chunk]:
    """Ingestion complète : renvoie tous les passages du corpus, prêts à indexer."""
    settings = settings or get_settings()
    metas: Dict[str, DocumentMeta] = load_registry()
    all_chunks: List[Chunk] = []

    for doc_id, meta in metas.items():
        pdf_path = settings.paths.corpus_dir / meta.source_file
        if not pdf_path.exists():
            if verbose:
                print(f"  ! fichier absent, ignoré : {meta.source_file}")
            continue
        elements = extract_document(pdf_path, meta)
        for el in elements:
            el.text = clean_text(el.text)
        doc_chunks = chunk_document(elements, meta, settings.ingestion)
        all_chunks.extend(doc_chunks)
        if verbose:
            n_tab = sum(c.is_table for c in doc_chunks)
            print(f"  - {doc_id:32s} [{meta.diffusion_status.value:8s}] "
                  f"{len(doc_chunks):3d} passages ({n_tab} tabulaires)")

    if verbose:
        print(f"  = total : {len(all_chunks)} passages issus de {len(metas)} documents")
    return all_chunks
