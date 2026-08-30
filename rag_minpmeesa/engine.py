"""
Moteur RAG de haut niveau (chapitre 3.1) : point d'entrée unique du système.

Assemble l'index, la récupération hybride et la restitution contrôlée en une
seule opération `query(texte, mode)`. C'est l'objet manipulé par les interfaces
(CLI, application web) et par le protocole d'évaluation.
"""
from __future__ import annotations

from typing import List, Optional

from .config import Mode, Settings, get_settings
from .schema import RetrievalResult
from .ingestion import build_chunks
from .index.store import IndexStore
from .retrieval.pipeline import HybridRetriever, RetrievalConfigRun, CONFIGS
from .retrieval.filters import Filter
from .generation.answer import Answerer, Answer


class RAGEngine:
    def __init__(self, settings: Settings | None = None, verbose: bool = False):
        self.settings = settings or get_settings()
        self.store: Optional[IndexStore] = None
        self.retriever: Optional[HybridRetriever] = None
        self.answerer = Answerer(self.settings)
        self._verbose = verbose

    # ---- cycle de vie de l'index ---------------------------------------- #
    def build_index(self, rebuild: bool = True) -> "RAGEngine":
        chunks = build_chunks(self.settings, verbose=self._verbose)
        self.store = IndexStore(self.settings).build(chunks, verbose=self._verbose)
        self.store.save()
        self.retriever = HybridRetriever(self.store, self.settings, verbose=self._verbose)
        return self

    def load_index(self) -> "RAGEngine":
        self.store = IndexStore(self.settings)
        if not self.store.exists():
            raise FileNotFoundError(
                "Index introuvable. Construisez-le d'abord : "
                "`python -m rag_minpmeesa.app.cli build`.")
        self.store.load()
        self.retriever = HybridRetriever(self.store, self.settings, verbose=self._verbose)
        return self

    def ensure_ready(self) -> "RAGEngine":
        if self.retriever is not None:
            return self
        store = IndexStore(self.settings)
        return self.load_index() if store.exists() else self.build_index()

    # ---- opérations ----------------------------------------------------- #
    def retrieve(self, query: str, mode: Mode = Mode.PRODUCTION,
                 run: Optional[RetrievalConfigRun] = None,
                 base_filter: Optional[Filter] = None,
                 top_k: Optional[int] = None) -> List[RetrievalResult]:
        self.ensure_ready()
        return self.retriever.retrieve(query, mode=mode, run=run,
                                       base_filter=base_filter, top_k=top_k)

    def query(self, query: str, mode: Mode = Mode.PRODUCTION,
              run: Optional[RetrievalConfigRun] = None,
              base_filter: Optional[Filter] = None) -> Answer:
        """Récupération hybride + restitution contrôlée : la réponse complète."""
        results = self.retrieve(query, mode=mode,
                                run=run or CONFIGS["hybride+rerank"],
                                base_filter=base_filter)
        return self.answerer.answer(query, results, mode=mode)
