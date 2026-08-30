"""
Chargement et exploitation du jeu de test annoté (chapitre 4.1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Mode, get_settings
from ..schema import Chunk


@dataclass
class GoldQuestion:
    id: str
    question: str
    mode: Mode
    relevant: List[dict]                       # [{doc_id, pages:[...]}]
    gold_numbers: List[str] = field(default_factory=list)
    reference: str = ""
    internal_only: bool = False

    def relevant_pages(self, doc_id: str) -> set:
        pages = set()
        for r in self.relevant:
            if r["doc_id"] == doc_id:
                pages.update(r["pages"])
        return pages

    @property
    def total_relevant_pages(self) -> int:
        return sum(len(r["pages"]) for r in self.relevant)


def load_gold(path=None) -> List[GoldQuestion]:
    settings = get_settings()
    path = path or (settings.paths.gold_dir / "gold_testset.json")
    data = json.loads(open(path, encoding="utf-8").read())
    out = []
    for q in data["questions"]:
        out.append(GoldQuestion(
            id=q["id"],
            question=q["question"],
            mode=Mode(q.get("mode", "production")),
            relevant=q["relevant"],
            gold_numbers=q.get("gold_numbers", []),
            reference=q.get("reference", ""),
            internal_only=q.get("internal_only", False),
        ))
    return out


def is_relevant(chunk: Chunk, gold: GoldQuestion) -> bool:
    """Un passage est pertinent si son document et sa plage de pages recoupent
    une annotation de référence (relevance au niveau document+page)."""
    pages = gold.relevant_pages(chunk.doc_id)
    if not pages:
        return False
    chunk_pages = set(range(chunk.page_start, chunk.page_end + 1))
    return bool(pages & chunk_pages)
