"""
Backend d'embedding vectoriel (chapitre 3.3), volontairement enfichable.

Le choix du modèle dense est un arbitrage soumis à l'encadreur (plan A.6) :
déploiement local souverain vs interface externe. Le système est donc conçu
pour être indépendant du modèle :

  1. TransformerEmbedding — modèle de phrases multilingue exécuté LOCALEMENT
     (fastembed/ONNX ou sentence-transformers). C'est la configuration de
     référence pour un déploiement souverain (aucune donnée ne sort du réseau).

  2. TfidfEmbedding — substitut hors-ligne de type LSA (TF-IDF mots + caractères
     réduit par SVD tronquée). Il ne requiert AUCUN téléchargement de modèle et
     garantit que toute la chaîne s'exécute et s'évalue même sans accès réseau.
     Il fournit un signal sémantique distinct de BM25 (synonymie via
     co-occurrence), ce qui suffit à démontrer l'apport de la fusion hybride.

Le mode "auto" essaie (1) puis bascule sur (2). Le backend effectivement utilisé
est journalisé et enregistré dans les métadonnées de l'index, pour la
reproductibilité des expériences du chapitre 4.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..config import EmbeddingConfig


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class EmbeddingBackend:
    """Interface commune. `name` identifie le backend dans les métadonnées."""
    name: str = "base"
    dim: int = 0

    def fit(self, texts: List[str]) -> "EmbeddingBackend":
        return self

    def encode_documents(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        # Par défaut, requêtes et documents partagent le même encodage.
        return self.encode_documents(texts)

    def save(self, path: Path) -> None:
        pass

    def load(self, path: Path) -> "EmbeddingBackend":
        return self


# --------------------------------------------------------------------------- #
#  1. Backend transformeur (déploiement souverain de référence)
# --------------------------------------------------------------------------- #
class TransformerEmbedding(EmbeddingBackend):
    def __init__(self, model_name: str, normalize: bool = True):
        self.model_name = model_name
        self.normalize = normalize
        self.name = f"transformer:{model_name}"
        self._model = None
        self._is_e5 = "e5" in model_name.lower()
        self._backend_lib = None
        self._init_model()

    def _init_model(self):
        # Essai 1 : fastembed (ONNX, léger, CPU).
        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(self.model_name)
            self._backend_lib = "fastembed"
            probe = next(iter(self._model.embed(["test"])))
            self.dim = int(len(probe))
            return
        except Exception:
            self._model = None
        # Essai 2 : sentence-transformers (PyTorch).
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._backend_lib = "sentence-transformers"
            self.dim = int(self._model.get_sentence_embedding_dimension())
            return
        except Exception as exc:  # pragma: no cover - dépend de l'environnement
            raise RuntimeError(
                f"Aucun backend transformeur disponible pour {self.model_name} : {exc}"
            )

    def _embed(self, texts: List[str], prefix: str) -> np.ndarray:
        if self._is_e5 and prefix:
            texts = [f"{prefix}: {t}" for t in texts]
        if self._backend_lib == "fastembed":
            vecs = np.array(list(self._model.embed(texts)), dtype=np.float32)
        else:
            vecs = np.array(self._model.encode(texts, show_progress_bar=False),
                            dtype=np.float32)
        if self.normalize:
            vecs = _l2_normalize(vecs)
        return vecs

    def encode_documents(self, texts: List[str]) -> np.ndarray:
        return self._embed(texts, "passage")

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        return self._embed(texts, "query")


# --------------------------------------------------------------------------- #
#  2. Backend TF-IDF/LSA hors-ligne (substitut souverain sans téléchargement)
# --------------------------------------------------------------------------- #
class TfidfEmbedding(EmbeddingBackend):
    def __init__(self, dims: int = 384, normalize: bool = True, seed: int = 42):
        self.dims = dims
        self.normalize = normalize
        self.seed = seed
        self.name = f"tfidf-lsa:{dims}"
        self.dim = dims
        self._vectorizer = None
        self._svd = None

    def _build(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import Normalizer
        from .text_utils import STOPWORDS_FR
        # Mots (1-2 grammes) + caractères (3-5 grammes) : capte la morphologie
        # française et une part de la synonymie, à la façon d'un LSA.
        word_vec = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2),
            min_df=1, max_df=0.9, sublinear_tf=True,
            stop_words=list(STOPWORDS_FR),
        )
        return word_vec, TruncatedSVD, make_pipeline, Normalizer

    def fit(self, texts: List[str]) -> "TfidfEmbedding":
        from sklearn.decomposition import TruncatedSVD
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import Normalizer
        word_vec, _, _, _ = self._build()
        self._vectorizer = word_vec
        X = self._vectorizer.fit_transform(texts)
        n_comp = min(self.dims, X.shape[1] - 1, max(2, X.shape[0] - 1))
        self.dim = n_comp
        svd = TruncatedSVD(n_components=n_comp, random_state=self.seed)
        norm = Normalizer(copy=False) if self.normalize else None
        self._svd = make_pipeline(svd, norm) if norm else make_pipeline(svd)
        self._svd.fit(X)
        return self

    def encode_documents(self, texts: List[str]) -> np.ndarray:
        if self._vectorizer is None:
            raise RuntimeError("TfidfEmbedding non ajusté : appelez fit() d'abord.")
        X = self._vectorizer.transform(texts)
        vecs = self._svd.transform(X).astype(np.float32)
        return vecs

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"vectorizer": self._vectorizer, "svd": self._svd,
                         "dim": self.dim, "dims": self.dims}, f)

    def load(self, path: Path) -> "TfidfEmbedding":
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._vectorizer = state["vectorizer"]
        self._svd = state["svd"]
        self.dim = state["dim"]
        self.dims = state["dims"]
        return self


# --------------------------------------------------------------------------- #
#  Fabrique
# --------------------------------------------------------------------------- #
def get_embedding_backend(cfg: EmbeddingConfig, verbose: bool = True) -> EmbeddingBackend:
    """Instancie le backend selon la configuration, avec bascule automatique."""
    def _log(msg):
        if verbose:
            print(msg)

    if cfg.backend in ("auto", "transformer"):
        try:
            be = TransformerEmbedding(cfg.transformer_model, normalize=cfg.normalize)
            _log(f"  [embedding] backend transformeur actif : {be.name} "
                 f"({be._backend_lib}, dim={be.dim})")
            return be
        except Exception as exc:
            if cfg.backend == "transformer":
                raise
            _log(f"  [embedding] transformeur indisponible ({type(exc).__name__}) "
                 f"-> bascule sur le substitut hors-ligne TF-IDF/LSA")

    be = TfidfEmbedding(dims=cfg.tfidf_dims, normalize=cfg.normalize)
    _log(f"  [embedding] backend hors-ligne actif : {be.name}")
    return be
