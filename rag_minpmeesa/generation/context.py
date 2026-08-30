"""
Construction du contexte de restitution (chapitre 3.5).

Les passages récupérés sont assemblés en un contexte numéroté [S1], [S2]… où
chaque bloc porte sa référence complète (document, page). Cette numérotation
sert d'ancrage : toute affirmation de la synthèse renvoie à un identifiant de
source, condition de la vérifiabilité (hypothèse H3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..schema import RetrievalResult


@dataclass
class ContextBlock:
    sid: str                 # "S1", "S2"…
    text: str
    citation: str
    result: RetrievalResult


def build_context(results: List[RetrievalResult],
                  max_chars: int = 6000) -> List[ContextBlock]:
    """Assemble les passages en blocs de contexte numérotés et bornés en taille."""
    blocks: List[ContextBlock] = []
    used = 0
    for i, res in enumerate(results, start=1):
        text = res.chunk.text.strip()
        if used + len(text) > max_chars and blocks:
            break
        blocks.append(ContextBlock(
            sid=f"S{i}",
            text=text,
            citation=res.chunk.citation(),
            result=res,
        ))
        used += len(text)
    return blocks


def render_context(blocks: List[ContextBlock]) -> str:
    """Rend le contexte sous forme textuelle (pour un LLM ou l'affichage)."""
    parts = []
    for b in blocks:
        parts.append(f"[{b.sid}] {b.citation}\n{b.text}")
    return "\n\n".join(parts)
