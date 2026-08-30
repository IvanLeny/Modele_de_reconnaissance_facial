"""
Segmentation en passages (chapitre 3.2).

Stratégie : fenêtre glissante par nombre de mots, avec recouvrement, guidée par
la structure. Les frontières de section et de page sont respectées autant que
possible pour ne pas séparer une donnée de son contexte immédiat. Les passages
denses en chiffres (tableaux) sont conservés d'un seul tenant sous un plafond de
taille, afin de ne jamais couper une ligne de chiffres de son en-tête.

Chaque passage reçoit un identifiant stable et hérite des métadonnées du
document (statut de diffusion, type, année, trimestre) : c'est ce qui permet
ensuite le filtrage par mode et la traçabilité de chaque citation.
"""
from __future__ import annotations

import re
from typing import List

from ..config import IngestionConfig
from ..schema import Chunk, DocumentMeta
from .extract import PageElement

_DIGIT_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"\S+")


def _count_numbers(text: str) -> bool:
    return len(_DIGIT_RE.findall(text)) >= 2


# Motif de légende de sommaire : « Tableau 4 : … » / « Graphique 2 : … »
_CAPTION_RE = re.compile(r"(Tableau|Graphique|Figure)\s+\d+\s*:", re.IGNORECASE)


def _is_toc(text: str) -> bool:
    """Détecte un passage de sommaire / liste des tableaux (navigationnel, non informatif)."""
    captions = _CAPTION_RE.findall(text)
    if len(captions) >= 3:
        # Beaucoup de légendes et peu de phrases : c'est une table des matières.
        return True
    return False


def _split_paragraphs(text: str) -> List[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(
    elements: List[PageElement],
    meta: DocumentMeta,
    cfg: IngestionConfig,
) -> List[Chunk]:
    """Segmente les éléments d'un document en passages indexables."""
    chunks: List[Chunk] = []
    counter = 0

    # On agrège paragraphe par paragraphe en respectant la taille cible.
    buffer_words: List[str] = []
    buffer_pages: List[int] = []
    buffer_section = ""
    buffer_is_table = False

    def flush():
        nonlocal counter, buffer_words, buffer_pages, buffer_section, buffer_is_table
        if not buffer_words:
            return
        text = " ".join(buffer_words).strip()
        wc = len(buffer_words)
        if wc >= cfg.min_chunk_words and not _is_toc(text):
            page_start = min(buffer_pages)
            page_end = max(buffer_pages)
            chunk_id = f"{meta.doc_id}::c{counter:04d}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=meta.doc_id,
                text=text,
                page_start=page_start,
                page_end=page_end,
                section=buffer_section,
                is_table=buffer_is_table or _count_numbers(text) and (
                    len(_DIGIT_RE.findall(text)) / max(1, len(text)) > 0.06),
                contains_numbers=_count_numbers(text),
                doc_title=meta.title,
                doc_type=meta.doc_type,
                diffusion_status=meta.diffusion_status,
                year=meta.year,
                quarter=meta.quarter,
                word_count=wc,
            ))
            counter += 1
        buffer_words = []
        buffer_pages = []
        buffer_is_table = False

    for el in elements:
        for para in _split_paragraphs(el.text):
            words = _WORD_RE.findall(para)
            if not words:
                continue
            para_is_table = el.is_table and (
                len(_DIGIT_RE.findall(para)) / max(1, len(para)) > 0.06)

            # Un tableau compact est émis d'un seul tenant.
            if para_is_table and len(words) <= cfg.table_max_words:
                flush()
                buffer_words = words
                buffer_pages = [el.page]
                buffer_section = el.section
                buffer_is_table = True
                flush()
                continue

            # Sinon, fenêtre glissante par mots.
            if not buffer_words:
                buffer_section = el.section
            if el.page not in buffer_pages:
                buffer_pages.append(el.page)
            buffer_words.extend(words)

            while len(buffer_words) >= cfg.chunk_size_words:
                head = buffer_words[:cfg.chunk_size_words]
                counter_before = counter
                # émettre 'head'
                saved_words = buffer_words
                buffer_words = head
                flush()
                # recouvrement : conserver la queue
                overlap = saved_words[cfg.chunk_size_words - cfg.chunk_overlap_words:]
                buffer_words = overlap
                buffer_pages = [el.page]
                buffer_section = el.section
        # frontière de section forte : on vide le tampon aux changements majeurs
        # (laissé au recouvrement naturel ; flush explicite en fin de doc)
    flush()
    return chunks
