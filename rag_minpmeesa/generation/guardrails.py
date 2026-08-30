"""
Garde-fous de qualité de la restitution (chapitre 3.6).

Deux garde-fous complémentaires :

  - Garde-fou NUMÉRIQUE (module numeric) : aucune donnée chiffrée non sourcée
    n'est présentée.
  - Garde-fou de FIDÉLITÉ (ce module) : chaque énoncé de la synthèse doit être
    soutenu par le contexte. On mesure le recouvrement lexical de chaque phrase
    avec l'ensemble des passages ; une phrase dont le recouvrement est inférieur
    au seuil est jugée « non soutenue ».

La proportion d'énoncés non soutenus est la grandeur visée par l'hypothèse H3
(l'ancrage documentaire doit la réduire de plus de 20 points) et la fidélité
moyenne (1 - part non soutenue) doit dépasser 0,80.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from ..index.text_utils import tokenize_fr


def split_sentences(text: str) -> List[str]:
    """Découpe naïf en phrases (français), suffisant pour l'audit de fidélité."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÉÈÀÂÎ0-9])", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 0]


def sentence_support(sentence: str, context_tokens: set) -> float:
    """Part des tokens de contenu de la phrase présents dans le contexte."""
    toks = [t for t in tokenize_fr(sentence)]
    if not toks:
        return 1.0
    covered = sum(1 for t in set(toks) if t in context_tokens)
    return covered / len(set(toks))


@dataclass
class FaithfulnessReport:
    n_sentences: int = 0
    n_supported: int = 0
    unsupported_sentences: List[str] = field(default_factory=list)

    @property
    def faithfulness(self) -> float:
        """Fidélité : part des énoncés soutenus par les sources."""
        return 1.0 if self.n_sentences == 0 else self.n_supported / self.n_sentences

    @property
    def unsupported_rate(self) -> float:
        return 0.0 if self.n_sentences == 0 else len(self.unsupported_sentences) / self.n_sentences

    def to_dict(self) -> dict:
        return {
            "n_sentences": self.n_sentences,
            "n_supported": self.n_supported,
            "faithfulness": round(self.faithfulness, 4),
            "unsupported_rate": round(self.unsupported_rate, 4),
            "unsupported_sentences": self.unsupported_sentences,
        }


def faithfulness_report(answer_text: str, context_texts: List[str],
                        threshold: float = 0.5) -> FaithfulnessReport:
    """Évalue la fidélité d'une réponse au regard du contexte fourni."""
    context_tokens = set()
    for c in context_texts:
        context_tokens.update(tokenize_fr(c))
    rep = FaithfulnessReport()
    for sent in split_sentences(answer_text):
        rep.n_sentences += 1
        if sentence_support(sent, context_tokens) >= threshold:
            rep.n_supported += 1
        else:
            rep.unsupported_sentences.append(sent)
    return rep
