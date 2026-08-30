"""
Métriques de récupération (chapitre 4.2).

Toutes prennent en entrée une liste booléenne `rels` indiquant, dans l'ordre du
classement renvoyé, si chaque passage est pertinent. On implémente :

  - Precision@k : part de pertinents dans les k premiers ;
  - Recall@k    : part des pertinents retrouvés dans les k premiers ;
  - MRR         : inverse du rang du premier pertinent ;
  - nDCG@k      : gain cumulé actualisé normalisé (tient compte de l'ordre).

Ces métriques sont standard pour l'évaluation de la recherche d'information et
fondent la validation des hypothèses H1 (fusion hybride) et H2 (reranking).
"""
from __future__ import annotations

import math
from typing import List


def precision_at_k(rels: List[bool], k: int) -> float:
    top = rels[:k]
    return sum(top) / k if k else 0.0


def recall_at_k(rels: List[bool], k: int, total_relevant: int) -> float:
    if total_relevant <= 0:
        return 0.0
    return sum(rels[:k]) / total_relevant


def mrr(rels: List[bool]) -> float:
    for i, r in enumerate(rels, start=1):
        if r:
            return 1.0 / i
    return 0.0


def dcg_at_k(rels: List[bool], k: int) -> float:
    dcg = 0.0
    for i, r in enumerate(rels[:k], start=1):
        if r:
            dcg += 1.0 / math.log2(i + 1)
    return dcg


def ndcg_at_k(rels: List[bool], k: int, total_relevant: int) -> float:
    ideal_hits = min(total_relevant, k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg_at_k(rels, k) / idcg
