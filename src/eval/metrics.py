"""
Métriques d'évaluation (cahier des charges, Étape 8).

Trois familles :
  - qualité rédactionnelle : ROUGE-1, ROUGE-2, ROUGE-L, similarité, contre le
    commentaire publié ;
  - ancrage : taux d'énoncés soutenus par le contexte, taux de citation ;
  - exactitude et couverture : exactitude numérique, couverture des indicateurs.

Toutes bornées à [0, 1] : une valeur > 1 signalerait une erreur de définition
(cahier des charges §6.4). La « similarité » hors-ligne est un substitut lexical
(Jaccard) ; la vraie similarité sémantique se calcule avec l'encodeur sur la
machine cible (même interface, valeur renseignée dans le régime de référence).
"""
from __future__ import annotations

from typing import List, Sequence

from ..retrieval.text import tokens as _tok_set
import re

_WORD = re.compile(r"[a-zA-Zà-ÿœæ0-9]+", re.IGNORECASE)


def _toks(text: str) -> List[str]:
    from ..retrieval.text import normalize
    return _WORD.findall(normalize(text))


def _ngrams(seq: Sequence[str], n: int):
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]


def rouge_n(candidat: str, reference: str, n: int = 1) -> float:
    """ROUGE-N en rappel (part des n-grammes de la référence retrouvés)."""
    ref = _ngrams(_toks(reference), n)
    cand = set(_ngrams(_toks(candidat), n))
    if not ref:
        return 0.0
    hits = sum(1 for g in ref if g in cand)
    return round(hits / len(ref), 4)


def _lcs(a: Sequence, b: Sequence) -> int:
    m, k = len(a), len(b)
    if m == 0 or k == 0:
        return 0
    dp = [0] * (k + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, k + 1):
            tmp = dp[j]
            dp[j] = prev + 1 if a[i - 1] == b[j - 1] else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[k]


def rouge_l(candidat: str, reference: str) -> float:
    """ROUGE-L en rappel (sous-séquence commune la plus longue / longueur réf)."""
    a, b = _toks(candidat), _toks(reference)
    if not b:
        return 0.0
    return round(_lcs(a, b) / len(b), 4)


def similarite_lexicale(candidat: str, reference: str) -> float:
    """Substitut hors-ligne de la similarité sémantique : Jaccard de tokens de
    contenu. Remplacé par la similarité cosinus de l'encodeur en régime référence."""
    ta, tb = _tok_set(candidat), _tok_set(reference)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)


def taux_soutenu(propositions: List[str], contexte: str, seuil: float = 0.4) -> float:
    """Ancrage : part des propositions dont le recouvrement de tokens avec le
    contexte dépasse le seuil."""
    if not propositions:
        return 1.0
    ctx = _tok_set(contexte)
    n_ok = 0
    for p in propositions:
        tp = _tok_set(p)
        if tp and len(tp & ctx) / len(tp) >= seuil:
            n_ok += 1
    return round(n_ok / len(propositions), 4)


def couverture(valeurs_citees: int, valeurs_disponibles: int) -> float:
    """Part des valeurs disponibles de l'exercice effectivement mobilisées."""
    if valeurs_disponibles <= 0:
        return 0.0
    return round(min(valeurs_citees, valeurs_disponibles) / valeurs_disponibles, 4)
