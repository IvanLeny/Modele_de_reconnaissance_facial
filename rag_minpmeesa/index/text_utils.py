"""
Prétraitement lexical pour l'indexation BM25 (chapitre 3.3).

Tokenisation adaptée au français : minuscule, retrait des accents pour la
robustesse aux variantes orthographiques, séparation sur la ponctuation,
conservation des nombres (essentiels pour un corpus statistique), retrait d'une
liste courte de mots vides. On évite toute racinisation agressive qui
fusionnerait des termes métier distincts.
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

# Mots vides français usuels (liste volontairement courte et conservatrice).
STOPWORDS_FR = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou",
    "a", "à", "au", "aux", "en", "dans", "sur", "sous", "par", "pour", "avec",
    "sans", "ce", "cet", "cette", "ces", "se", "sa", "son", "ses", "leur",
    "leurs", "que", "qui", "quoi", "dont", "est", "sont", "ont", "aux", "il",
    "elle", "ils", "elles", "on", "nous", "vous", "ne", "pas", "plus", "au",
    "the", "of", "and", "in", "to",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,]\d+)?", re.IGNORECASE)


def normalize(text: str) -> str:
    """Minuscule + suppression des accents (comparaison robuste)."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def tokenize_fr(text: str, keep_stopwords: bool = False) -> List[str]:
    """Tokenise un texte français en conservant les nombres décimaux (1,5 / 3.2)."""
    norm = normalize(text)
    tokens = _TOKEN_RE.findall(norm)
    if keep_stopwords:
        return tokens
    return [t for t in tokens if t not in STOPWORDS_FR and len(t) > 1 or t.isdigit()]
