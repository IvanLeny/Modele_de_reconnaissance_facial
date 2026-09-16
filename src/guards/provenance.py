"""
Traçabilité des énoncés (cahier des charges, Étape 7.2).

Deux niveaux de provenance :
  - une proposition qui **cite une valeur** renvoie au tableau de l'Annuaire
    d'où provient la valeur (source de données) ;
  - une proposition d'**interprétation** (sans valeur, ou tournure reprise d'un
    commentaire antérieur) renvoie au commentaire antérieur dont elle reprend la
    formulation (source de forme).

La provenance est attachée à chaque proposition retenue, pour affichage dans
l'interface (Étape 10) et pour le calcul du taux de citation (Étape 8).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .numeric import Proposition, extract_numbers
from ..retrieval.text import jaccard_tokens


@dataclass
class SourceRef:
    """Référence d'une source : document, exercice, section, page."""
    doc_id: str
    exercice: Optional[int]
    section: str = ""
    page: Optional[int] = None

    def libelle(self) -> str:
        bits = [self.doc_id]
        if self.exercice:
            bits.append(f"exercice {self.exercice}")
        if self.section:
            bits.append(self.section)
        if self.page:
            bits.append(f"p. {self.page}")
        return ", ".join(bits)


@dataclass
class PropositionTracee:
    proposition: Proposition
    niveau: str                       # "donnée" | "interprétation"
    source: Optional[SourceRef]

    def to_dict(self) -> dict:
        return {"texte": self.proposition.texte, "niveau": self.niveau,
                "source": self.source.libelle() if self.source else ""}


def tracer(proposition: Proposition,
           source_donnees: Optional[SourceRef],
           commentaires_anterieurs: Optional[List[tuple]] = None) -> PropositionTracee:
    """Attache la provenance à une proposition.

    `commentaires_anterieurs` : liste de (texte, SourceRef) des commentaires
    homologues antérieurs, pour retrouver la formulation reprise par une
    proposition d'interprétation.
    """
    if extract_numbers(proposition.texte):
        # Porte au moins une valeur -> source de données (tableau de l'Annuaire).
        return PropositionTracee(proposition, "donnée", source_donnees)
    # Interprétation : on relie au commentaire antérieur le plus proche.
    best_src, best_ov = None, 0.0
    for texte, ref in (commentaires_anterieurs or []):
        ov = jaccard_tokens(proposition.texte, texte)
        if ov > best_ov:
            best_ov, best_src = ov, ref
    return PropositionTracee(proposition, "interprétation", best_src or source_donnees)
