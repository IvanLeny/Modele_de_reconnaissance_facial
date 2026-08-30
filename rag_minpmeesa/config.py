"""
Configuration centrale du système (chapitre 3.1).

Regroupe en un point unique :
  - les deux modes d'usage et la règle de cloisonnement par statut de diffusion ;
  - les paramètres d'ingestion (segmentation) ;
  - les paramètres de récupération (BM25, vectoriel, fusion RRF, reranking) ;
  - la règle de restitution contrôlée (citation littérale des données chiffrées) ;
  - les seuils de validation des hypothèses fixés *a priori* (Tableau A.3).

Aucune valeur n'est codée en dur ailleurs : tout paramètre expérimental est
défini ici de façon à garantir la reproductibilité des expériences du chapitre 4.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


# --------------------------------------------------------------------------- #
#  Modes d'usage et statut de diffusion (plan A.2)
# --------------------------------------------------------------------------- #
class Mode(str, Enum):
    """Les deux modes d'usage du système (Tableau A.1)."""
    PRODUCTION = "production"      # amont : agents ; corpus interne + publié
    CONSULTATION = "consultation"  # aval  : décideurs ; corpus publié uniquement


class DiffusionStatus(str, Enum):
    """Statut de diffusion d'un document — porte le cloisonnement des modes."""
    INTERNE = "interne"    # document de travail non validé, réservé au mode production
    PUBLIE = "publie"      # document édité et validé, accessible aux deux modes


# Corpus visible par chaque mode. Le mode consultation ne voit JAMAIS l'interne.
MODE_VISIBILITY = {
    Mode.PRODUCTION: {DiffusionStatus.INTERNE, DiffusionStatus.PUBLIE},
    Mode.CONSULTATION: {DiffusionStatus.PUBLIE},
}


# --------------------------------------------------------------------------- #
#  Chemins
# --------------------------------------------------------------------------- #
_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Paths:
    root: Path = _ROOT
    corpus_dir: Path = _ROOT / "data" / "corpus"
    registry_file: Path = _ROOT / "data" / "corpus" / "registry.json"
    index_dir: Path = _ROOT / "data" / "index"
    gold_dir: Path = _ROOT / "data" / "gold"
    results_dir: Path = _ROOT / "data" / "results"

    def ensure(self) -> "Paths":
        for p in (self.index_dir, self.gold_dir, self.results_dir):
            p.mkdir(parents=True, exist_ok=True)
        return self


# --------------------------------------------------------------------------- #
#  Paramètres d'ingestion (chapitre 3.2)
# --------------------------------------------------------------------------- #
@dataclass
class IngestionConfig:
    # Segmentation : fenêtre glissante par nombre de mots, avec recouvrement.
    # Une segmentation modérée préserve le contexte d'un tableau tout en gardant
    # des passages assez fins pour la précision de récupération.
    chunk_size_words: int = 180
    chunk_overlap_words: int = 40
    min_chunk_words: int = 12          # rejette les fragments trop courts (titres isolés)
    # Un tableau détecté est conservé d'un seul tenant s'il tient sous cette taille,
    # afin de ne jamais scinder une ligne de chiffres de son en-tête.
    table_max_words: int = 320


# --------------------------------------------------------------------------- #
#  Paramètres d'indexation et de récupération (chapitres 3.3, 3.4)
# --------------------------------------------------------------------------- #
@dataclass
class EmbeddingConfig:
    # Modèle dense privilégié pour un déploiement local et souverain.
    # Multilingue (français) et léger (384 dims), exécutable sur CPU.
    transformer_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Backend : "auto" essaie le transformeur puis bascule sur le substitut TF-IDF
    # hors-ligne si aucun modèle n'est disponible (voir index/embeddings.py).
    backend: str = "auto"              # {"auto", "transformer", "tfidf"}
    tfidf_dims: int = 384              # dimension du substitut hors-ligne (SVD tronquée)
    normalize: bool = True             # vecteurs L2-normalisés -> cosinus = produit scalaire


@dataclass
class RetrievalConfig:
    top_k_lexical: int = 30            # candidats BM25
    top_k_vector: int = 30            # candidats vectoriels
    rrf_k: int = 60                   # constante de la Reciprocal Rank Fusion
    top_k_fused: int = 12            # candidats après fusion, transmis au reranking
    top_k_final: int = 5             # passages retenus pour la restitution
    use_reranker: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Poids du score de reranking dans le classement final ; le complément
    # (1 - poids) revient au score de fusion de premier étage (prior de
    # récupération). Un reranking pur (poids = 1) peut dégrader le rappel ;
    # le mélange stabilise le classement (learning-to-rank à deux étages).
    rerank_blend: float = 0.5


# --------------------------------------------------------------------------- #
#  Restitution contrôlée (chapitres 3.5, 3.6)
# --------------------------------------------------------------------------- #
@dataclass
class GenerationConfig:
    # Règle de conception centrale (plan A.2) : toute donnée chiffrée présente
    # dans une synthèse doit être reprise LITTÉRALEMENT d'un passage source
    # (sans reformulation, recalcul ni arrondi) et accompagnée de sa référence.
    enforce_literal_numbers: bool = True
    # Mode de rédaction du résumé :
    #   "extractive" : synthèse par sélection de phrases sourcées (100 % local,
    #                  aucune hallucination possible — c'est le défaut souverain) ;
    #   "llm"        : rédaction par un modèle de langage, sous contrainte des
    #                  garde-fous numériques (à activer avec un LLM local type Ollama).
    synthesis: str = "extractive"
    max_context_chars: int = 6000
    max_summary_sentences: int = 5
    # Un énoncé de la synthèse est jugé « soutenu » si son recouvrement lexical
    # avec le contexte dépasse ce seuil (garde-fou de fidélité, chap. 3.6).
    support_overlap_threshold: float = 0.5


# --------------------------------------------------------------------------- #
#  Seuils de validation des hypothèses fixés a priori (Tableau A.3)
# --------------------------------------------------------------------------- #
@dataclass
class HypothesisThresholds:
    # H1 : hybride > meilleure config simple
    h1_min_ndcg_gain: float = 0.05
    h1_min_mrr_gain: float = 0.05
    # H2 : filtrage métadonnées + reranking > hybride sans reranking
    h2_min_ndcg_gain: float = 0.03
    h2_min_precision_gain: float = 0.03
    # H3 : ancrage documentaire
    h3_min_unsupported_reduction: float = 0.20   # -20 points de pourcentage
    h3_min_faithfulness: float = 0.80
    h3_min_numeric_accuracy: float = 0.95
    # H4 / H5 : gain de temps (protocole terrain — critères, non exécutés ici)
    h4_min_time_reduction: float = 0.50
    h5_min_time_reduction: float = 0.50
    h5_min_answer_accuracy: float = 0.85


# --------------------------------------------------------------------------- #
#  Agrégat
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    paths: Paths = field(default_factory=Paths)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    thresholds: HypothesisThresholds = field(default_factory=HypothesisThresholds)
    seed: int = 42

    def visible_status(self, mode: Mode) -> set:
        return MODE_VISIBILITY[Mode(mode)]

    def to_dict(self) -> dict:
        d = asdict(self)
        # Path -> str pour sérialisation JSON
        d["paths"] = {k: str(v) for k, v in d["paths"].items()}
        return d


_SETTINGS: Optional[Settings] = None


def get_settings() -> Settings:
    """Renvoie l'instance de configuration (singleton) et crée les dossiers."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
        _SETTINGS.paths.ensure()
        # Autorise un backend d'embedding forcé par variable d'environnement,
        # utile pour reproduire une expérience hors-ligne : RAG_EMBEDDING_BACKEND=tfidf
        env_backend = os.environ.get("RAG_EMBEDDING_BACKEND")
        if env_backend in {"auto", "transformer", "tfidf"}:
            _SETTINGS.embedding.backend = env_backend
    return _SETTINGS
