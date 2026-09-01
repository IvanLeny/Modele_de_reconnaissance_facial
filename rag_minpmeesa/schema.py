"""
Modèle de données commun à toute la chaîne (chapitre 3.2, métadonnées).

Trois objets structurent le flux :
    Document        -> un fichier source du patrimoine documentaire ;
    Chunk           -> un passage segmenté, unité d'indexation et de citation ;
    RetrievalResult -> un passage récupéré, assorti de son score et de sa provenance.

Le schéma de métadonnées est volontairement explicite : la traçabilité
(document, page, tableau) et le cloisonnement (statut de diffusion) sont des
exigences de conception, pas des ajouts optionnels.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .config import DiffusionStatus


@dataclass
class DocumentMeta:
    """Métadonnées de niveau document (renseignées dans le registre du corpus)."""
    doc_id: str                       # identifiant stable (nom de fichier sans extension)
    title: str
    source_file: str
    doc_type: str                     # "annuaire_statistique" | "note_conjoncture" | ...
    diffusion_status: DiffusionStatus = DiffusionStatus.PUBLIE
    year: Optional[int] = None
    quarter: Optional[str] = None     # ex. "T1", "T3"
    publisher: str = "MINPMEESA / DEPP"
    language: str = "fr"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["diffusion_status"] = self.diffusion_status.value
        return d


@dataclass
class Chunk:
    """Passage segmenté : unité atomique d'indexation et de citation."""
    chunk_id: str
    doc_id: str
    text: str
    page_start: int
    page_end: int
    # Métadonnées de structure (chap. 3.3) : servent au filtrage et au reranking.
    section: str = ""
    is_table: bool = False
    contains_numbers: bool = False
    # Métadonnées héritées du document (dénormalisées pour le filtrage rapide).
    doc_title: str = ""
    doc_type: str = ""
    diffusion_status: DiffusionStatus = DiffusionStatus.PUBLIE
    year: Optional[int] = None
    quarter: Optional[str] = None
    word_count: int = 0
    # Indice d'informativité du passage dans [0,1] (chap. 3.2) : distingue un
    # passage porteur d'information (prose rédigée ou tableau chiffré) d'un
    # passage « creux » (sommaire, formulaire d'annexe, liste d'intitulés vides).
    # Sert de prior de qualité au classement (retrieval/pipeline.py).
    informativeness: float = 1.0

    def citation(self) -> str:
        """Référence lisible d'une citation, apposée à chaque restitution."""
        pages = (f"p. {self.page_start}"
                 if self.page_start == self.page_end
                 else f"p. {self.page_start}-{self.page_end}")
        return f"[{self.doc_title}, {pages}]"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["diffusion_status"] = self.diffusion_status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        d = dict(d)
        d["diffusion_status"] = DiffusionStatus(d.get("diffusion_status", "publie"))
        return cls(**d)


@dataclass
class RetrievalResult:
    """Passage récupéré, enrichi des traces de scoring (chap. 3.4)."""
    chunk: Chunk
    score: float = 0.0                # score final (après fusion / reranking)
    rank_lexical: Optional[int] = None
    rank_vector: Optional[int] = None
    score_lexical: Optional[float] = None
    score_vector: Optional[float] = None
    score_rerank: Optional[float] = None
    provenance: str = ""             # "lexical" | "vector" | "fusion" | "rerank"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk"] = self.chunk.to_dict()
        return d
