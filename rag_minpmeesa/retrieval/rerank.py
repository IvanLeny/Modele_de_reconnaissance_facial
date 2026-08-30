"""
Réordonnancement (reranking) des candidats fusionnés (chapitre 3.4).

Le reranking affine le classement des quelques passages les mieux fusionnés en
les jugeant conjointement avec la requête, là où la première récupération les
évalue indépendamment. Deux implémentations, même interface :

  1. CrossEncoderReranker — un cross-encodeur (requête, passage) -> pertinence,
     modèle exécuté localement. C'est la configuration de référence.

  2. FeatureReranker — réordonnanceur hors-ligne fondé sur des traits explicites
     (couverture des termes de la requête, correspondance de phrase exacte,
     concordance des nombres, proximité, indice de section). Il ne requiert aucun
     téléchargement et fournit un signal d'appariement fin, distinct de la
     première récupération, ce qui permet d'évaluer l'apport du reranking (H2)
     même hors-ligne.

Le mode "auto" essaie (1) puis bascule sur (2).
"""
from __future__ import annotations

import math
import re
from typing import List, Tuple

from ..config import RetrievalConfig
from ..schema import Chunk
from ..index.text_utils import tokenize_fr, normalize

_NUM_RE = re.compile(r"\d[\d  .,]*\d|\d")


class Reranker:
    name = "base"

    def score(self, query: str, chunks: List[Chunk]) -> List[float]:
        raise NotImplementedError


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder  # peut échouer hors-ligne
        self._model = CrossEncoder(model_name)
        self.name = f"cross-encoder:{model_name}"

    def score(self, query: str, chunks: List[Chunk]) -> List[float]:
        pairs = [(query, c.text) for c in chunks]
        return [float(s) for s in self._model.predict(pairs)]


class FeatureReranker(Reranker):
    """Réordonnanceur hors-ligne à traits explicites (sans apprentissage)."""
    name = "feature-reranker"

    def __init__(self, corpus_texts: List[str] | None = None):
        # IDF approché sur le corpus, pour pondérer les termes rares de la requête.
        self._idf = {}
        if corpus_texts:
            self._fit_idf(corpus_texts)

    def _fit_idf(self, texts: List[str]):
        from collections import Counter
        df = Counter()
        n = len(texts)
        for t in texts:
            for tok in set(tokenize_fr(t)):
                df[tok] += 1
        self._idf = {tok: math.log((1 + n) / (1 + d)) + 1.0 for tok, d in df.items()}

    def _idf_of(self, tok: str) -> float:
        return self._idf.get(tok, 1.0)

    def score(self, query: str, chunks: List[Chunk]) -> List[float]:
        q_tokens = tokenize_fr(query)
        q_set = set(q_tokens)
        q_norm = normalize(query)
        q_numbers = set(_NUM_RE.findall(q_norm))
        total_idf = sum(self._idf_of(t) for t in q_set) or 1.0

        scores = []
        for c in chunks:
            c_norm = normalize(c.text)
            c_tokens = tokenize_fr(c.text)
            c_set = set(c_tokens)

            # (a) couverture pondérée par IDF des termes de la requête
            covered = sum(self._idf_of(t) for t in q_set if t in c_set)
            coverage = covered / total_idf

            # (b) correspondance de phrase exacte (bigrammes de la requête)
            bonus_phrase = 0.0
            for i in range(len(q_tokens) - 1):
                bg = q_tokens[i] + " " + q_tokens[i + 1]
                if bg in c_norm:
                    bonus_phrase += 0.15

            # (c) concordance des nombres présents dans la requête
            bonus_num = 0.0
            if q_numbers:
                matched = sum(1 for num in q_numbers if num and num in c_norm)
                bonus_num = 0.3 * (matched / len(q_numbers))

            # (d) indice de section : la requête mentionne un intitulé du passage
            bonus_section = 0.1 if c.section and normalize(c.section) in q_norm else 0.0

            # (e) légère préférence pour les passages tabulaires si la requête est chiffrée
            bonus_table = 0.05 if (q_numbers and c.is_table) else 0.0

            scores.append(coverage + bonus_phrase + bonus_num + bonus_section + bonus_table)
        return scores


def get_reranker(cfg: RetrievalConfig, corpus_texts: List[str] | None = None,
                 verbose: bool = True) -> Reranker:
    """Instancie le reranker selon la configuration, avec bascule automatique."""
    try:
        rr = CrossEncoderReranker(cfg.reranker_model)
        if verbose:
            print(f"  [rerank] cross-encodeur actif : {rr.name}")
        return rr
    except Exception as exc:
        if verbose:
            print(f"  [rerank] cross-encodeur indisponible ({type(exc).__name__}) "
                  f"-> réordonnanceur hors-ligne à traits")
        return FeatureReranker(corpus_texts)
