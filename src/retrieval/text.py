"""
Utilitaires de texte partagés (tokenisation française, similarité lexicale).

Sans dépendance externe : sert la traçabilité (rapprochement de formulations) et
le déclencheur d'abstention (faiblesse du contexte).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Set

_WORD_RE = re.compile(r"[a-zA-Zà-ÿœæ]+", re.IGNORECASE)

# Mots-outils français les plus fréquents (liste courte, suffisante pour la
# similarité de contenu ; pas de valeur expérimentale ici).
_STOP = {
    "le", "la", "les", "un", "une", "des", "de", "du", "d", "l", "et", "en",
    "au", "aux", "à", "dans", "par", "pour", "sur", "se", "sa", "son", "ses",
    "ce", "cette", "ces", "que", "qui", "est", "sont", "a", "ont", "plus",
    "moins", "the", "of",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def tokens(text: str) -> Set[str]:
    return {w for w in _WORD_RE.findall(normalize(text)) if w not in _STOP and len(w) > 2}


def jaccard_tokens(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0
