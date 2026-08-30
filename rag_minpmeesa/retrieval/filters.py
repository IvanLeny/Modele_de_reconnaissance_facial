"""
Filtrage par métadonnées et cloisonnement des modes (chapitres 3.4 et A.2).

Le filtre remplit deux fonctions distinctes :
  1. Filtre de RECHERCHE : restreindre la récupération à un type de document, une
     année, un trimestre… (améliore la précision, hypothèse H2).
  2. Mécanisme de CLOISONNEMENT : en mode consultation, interdire l'accès aux
     documents internes non validés. C'est une garantie de sécurité, appliquée
     AVANT tout scoring, jamais un simple tri a posteriori.

Le filtre s'applique en amont de la fusion : chaque canal (lexical, vectoriel)
ne voit que les passages autorisés.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from ..config import Mode, DiffusionStatus, MODE_VISIBILITY
from ..schema import Chunk


@dataclass
class Filter:
    """Prédicat de filtrage combinant cloisonnement et critères de recherche."""
    allowed_status: Set[DiffusionStatus] = field(
        default_factory=lambda: {DiffusionStatus.PUBLIE})
    doc_types: Optional[Set[str]] = None
    doc_ids: Optional[Set[str]] = None
    years: Optional[Set[int]] = None
    quarters: Optional[Set[str]] = None
    tables_only: bool = False
    numbers_only: bool = False

    def allows(self, chunk: Chunk) -> bool:
        if chunk.diffusion_status not in self.allowed_status:
            return False
        if self.doc_types and chunk.doc_type not in self.doc_types:
            return False
        if self.doc_ids and chunk.doc_id not in self.doc_ids:
            return False
        if self.years and chunk.year not in self.years:
            return False
        if self.quarters and chunk.quarter not in self.quarters:
            return False
        if self.tables_only and not chunk.is_table:
            return False
        if self.numbers_only and not chunk.contains_numbers:
            return False
        return True

    def allowed_indices(self, chunks: List[Chunk]) -> Set[int]:
        return {i for i, c in enumerate(chunks) if self.allows(c)}


def mode_filter(mode: Mode, base: Optional[Filter] = None) -> Filter:
    """Construit un filtre dont le cloisonnement correspond au mode d'usage."""
    f = base or Filter()
    f.allowed_status = set(MODE_VISIBILITY[Mode(mode)])
    return f
