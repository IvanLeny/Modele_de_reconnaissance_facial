"""
Fusion des classements par Reciprocal Rank Fusion (chapitre 3.4).

La RRF (Cormack et al., 2009) combine plusieurs classements sans nécessiter de
normaliser des scores d'échelles différentes (BM25 vs cosinus). Chaque passage
reçoit la somme, sur les canaux où il apparaît, de 1 / (k + rang). C'est une
méthode simple, robuste et sans paramètre à apprendre — bien adaptée à la
combinaison d'un canal lexical et d'un canal sémantique.

    score_RRF(d) = Σ_canaux  1 / (k + rang_canal(d))

Un rang élevé (mauvais) contribue peu ; un passage bien classé par les deux
canaux domine — ce qui matérialise la complémentarité recherchée (hypothèse H1).
"""
from __future__ import annotations

from typing import Dict, List, Tuple


def reciprocal_rank_fusion(
    ranked_lists: Dict[str, List[Tuple[int, float]]],
    k: int = 60,
) -> Dict[int, dict]:
    """
    Fusionne plusieurs classements.

    Paramètres
    ----------
    ranked_lists : {nom_canal: [(idx, score_brut), ...]}  triés par pertinence.
    k            : constante d'amortissement de la RRF.

    Retour
    ------
    {idx: {"rrf": score, "ranks": {canal: rang}, "scores": {canal: score_brut}}}
    """
    fused: Dict[int, dict] = {}
    for channel, ranked in ranked_lists.items():
        for rank, (idx, raw) in enumerate(ranked, start=1):
            entry = fused.setdefault(idx, {"rrf": 0.0, "ranks": {}, "scores": {}})
            entry["rrf"] += 1.0 / (k + rank)
            entry["ranks"][channel] = rank
            entry["scores"][channel] = raw
    return fused
