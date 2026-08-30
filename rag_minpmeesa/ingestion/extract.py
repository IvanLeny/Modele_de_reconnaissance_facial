"""
Extraction du texte des PDF (chapitre 3.2).

Choix techniques :
  - PyMuPDF en mode lecture (`sort=True`) restitue le texte dans l'ordre de
    lecture, en conservant les nombres des tableaux au voisinage de leurs
    libellés — condition nécessaire à la règle de citation littérale (3.6).
  - Les en-têtes et pieds de page répétés (titre courant, numéro de page) sont
    retirés : ils créeraient sinon des passages redondants et bruités.
  - Le repérage des sections (titres numérotés, intitulés en capitales, tableaux
    et graphiques) alimente la métadonnée `section` utilisée au reranking.

Le module renvoie une liste d'« éléments » {page, text, section, is_table}
qui seront ensuite nettoyés puis segmentés.

NB : une extraction fine de la structure tabulaire (PyMuPDF-layout, Camelot)
constitue un point d'extension documenté ; le mode texte suffit ici car les
notes de conjoncture et l'annuaire linéarisent déjà leurs tableaux.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pymupdf

from ..schema import DocumentMeta


@dataclass
class PageElement:
    page: int
    text: str
    section: str
    is_table: bool


_SECTION_PATTERNS = [
    re.compile(r"^\s*(\d+(?:\.\d+){0,2})\.?\s+[A-ZÉÈÀÂ].{3,80}$"),  # 1. / 1.2 / 2.3.1 Titre
    re.compile(r"^\s*(CHAPITRE|SECTION|PARTIE)\b.{0,80}$", re.IGNORECASE),
    re.compile(r"^\s*(Tableau|Graphique|Figure|Encadré)\s*\d+\b.{0,80}$", re.IGNORECASE),
]

_DIGIT_RE = re.compile(r"\d")


def _detect_repeated_lines(pages_lines: List[List[str]], min_ratio: float = 0.5) -> set:
    """Détecte les lignes récurrentes (en-têtes/pieds) présentes sur >= min_ratio des pages."""
    n = len(pages_lines)
    if n < 4:
        return set()
    counter: Counter = Counter()
    for lines in pages_lines:
        # bords de page : 3 premières et 3 dernières lignes
        for ln in lines[:3] + lines[-3:]:
            norm = ln.strip()
            if 3 <= len(norm) <= 90 and not norm.isdigit():
                counter[norm] += 1
    return {ln for ln, c in counter.items() if c >= max(3, int(min_ratio * n))}


def _looks_like_section(line: str) -> bool:
    s = line.strip()
    if len(s) < 4 or len(s) > 90:
        return False
    for pat in _SECTION_PATTERNS:
        if pat.match(s):
            return True
    # Ligne courte en capitales (intitulé de rubrique)
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.85 and len(s) <= 70:
        return True
    return False


def _ordered_page_text(page) -> str:
    """
    Reconstitue le texte d'une page dans l'ordre de lecture en tenant compte des
    colonnes. Les mises en page à deux colonnes (fréquentes dans les notes de
    conjoncture) sont détectées par la position horizontale des blocs : la
    colonne de gauche est lue en entier, puis celle de droite — ce qui évite
    l'entrelacement de phrases de colonnes différentes.
    """
    blocks = [b for b in page.get_text("blocks") if b[4].strip()]
    if not blocks:
        return page.get_text("text", sort=True)

    page_mid = page.rect.width / 2.0
    centers = [((b[0] + b[2]) / 2.0) for b in blocks]
    left = [c < page_mid * 0.85 for c in centers]
    right = [c > page_mid * 1.15 for c in centers]
    two_col = sum(left) >= 3 and sum(right) >= 3

    if two_col:
        left_blocks = sorted((b for b, c in zip(blocks, centers) if c < page_mid),
                             key=lambda b: b[1])
        right_blocks = sorted((b for b, c in zip(blocks, centers) if c >= page_mid),
                              key=lambda b: b[1])
        ordered = left_blocks + right_blocks
    else:
        ordered = sorted(blocks, key=lambda b: (round(b[1] / 3), b[0]))

    return "\n".join(b[4].strip() for b in ordered)


def extract_document(pdf_path: Path, meta: DocumentMeta) -> List[PageElement]:
    """Extrait le document en éléments de page, nettoyés des lignes récurrentes."""
    doc = pymupdf.open(pdf_path)
    pages_lines: List[List[str]] = []
    for page in doc:
        raw = _ordered_page_text(page)
        pages_lines.append(raw.splitlines())

    repeated = _detect_repeated_lines(pages_lines)

    elements: List[PageElement] = []
    current_section = ""
    for pindex, lines in enumerate(pages_lines, start=1):
        kept: List[str] = []
        for ln in lines:
            norm = ln.strip()
            if not norm:
                kept.append("")
                continue
            if norm in repeated:
                continue
            if norm.isdigit() and len(norm) <= 3:   # numéro de page isolé
                continue
            if _looks_like_section(norm):
                current_section = norm
            kept.append(ln)
        page_text = "\n".join(kept)
        # Densité de chiffres -> heuristique de tableau/données chiffrées
        digits = len(_DIGIT_RE.findall(page_text))
        is_table = digits > 0 and (digits / max(1, len(page_text))) > 0.06
        elements.append(PageElement(
            page=pindex,
            text=page_text,
            section=current_section,
            is_table=is_table,
        ))
    return elements
