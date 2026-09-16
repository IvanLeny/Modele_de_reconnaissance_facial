"""
Extraction PDF avec position des blocs (cahier des charges, Étape 1.2).

L'accès à la position est nécessaire pour :
  - reconstituer l'ordre de lecture des mises en page à plusieurs colonnes ;
  - repérer par récurrence les titres courants et numéros de page (Étape 1.3).

Aucune dépendance réseau. S'appuie sur PyMuPDF (pymupdf).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pymupdf


@dataclass
class Block:
    """Bloc de texte positionné sur une page."""
    page: int                      # numéro de page (1-indexé)
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0


@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Document:
    path: str
    pages: List[Page]

    def full_text(self) -> str:
        return "\n".join(b.text for p in self.pages for b in p.blocks)


def extract_document(path: str | Path) -> Document:
    """Ouvre un PDF et renvoie ses pages avec blocs positionnés."""
    path = str(path)
    doc = pymupdf.open(path)
    pages: List[Page] = []
    for i, page in enumerate(doc, start=1):
        rect = page.rect
        blocks: List[Block] = []
        for b in page.get_text("blocks"):
            # b = (x0, y0, x1, y1, "texte", block_no, block_type)
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            text = (text or "").strip()
            if not text:
                continue
            blocks.append(Block(page=i, x0=x0, y0=y0, x1=x1, y1=y1, text=text))
        pages.append(Page(number=i, width=rect.width, height=rect.height, blocks=blocks))
    doc.close()
    return Document(path=path, pages=pages)


def _norm(s: str) -> str:
    """Normalisation légère pour comparer des lignes récurrentes."""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\d+", "#", s)          # les numéros de page varient -> masqués
    return s


def detect_running_lines(doc: Document, min_ratio: float = 0.5) -> set:
    """Repère les titres courants et numéros de page : courtes lignes qui
    reviennent (à numéro près) sur au moins `min_ratio` des pages."""
    n_pages = max(1, len(doc.pages))
    counter: Counter = Counter()
    for p in doc.pages:
        seen = set()
        for b in p.blocks:
            for line in b.text.splitlines():
                line = line.strip()
                if not line or len(line) > 90:      # un titre courant est court
                    continue
                key = _norm(line)
                if key and key not in seen:
                    seen.add(key)
                    counter[key] += 1
    threshold = max(2, int(min_ratio * n_pages))
    return {k for k, c in counter.items() if c >= threshold}


def ordered_page_text(page: Page, running: set | None = None) -> str:
    """Texte d'une page dans l'ordre de lecture, colonnes gérées et titres
    courants retirés. Deux colonnes détectées par la position horizontale."""
    running = running or set()
    blocks = [b for b in page.blocks if _norm_first_line(b) not in running]
    if not blocks:
        return ""
    mid = page.width / 2.0
    # Une page est « à deux colonnes » si des blocs se tiennent nettement de part
    # et d'autre du milieu sans le chevaucher.
    left = [b for b in blocks if b.x1 <= mid + page.width * 0.05]
    right = [b for b in blocks if b.x0 >= mid - page.width * 0.05]
    two_col = len(left) >= 2 and len(right) >= 2 and (len(left) + len(right) >= len(blocks) * 0.7)
    if two_col:
        left.sort(key=lambda b: b.y0)
        right.sort(key=lambda b: b.y0)
        ordered = left + right
    else:
        ordered = sorted(blocks, key=lambda b: (round(b.y0), b.x0))
    return "\n".join(b.text for b in ordered)


def _norm_first_line(b: Block) -> str:
    first = b.text.splitlines()[0] if b.text.splitlines() else ""
    return _norm(first)
