"""
rag_minpmeesa
=============

Système de génération augmentée par récupération (RAG) hybride pour
l'exploitation du patrimoine documentaire du MINPMEESA, en appui à la
production de l'Annuaire statistique des PMEESA et du Rapport annuel de
performance (RAP).

Ce paquet implémente l'artefact décrit au chapitre 3 du mémoire :

    3.1  Architecture générale et environnement technique      -> config, pipeline
    3.2  Ingestion : extraction, nettoyage, segmentation        -> ingestion/
    3.3  Indexation lexicale et vectorielle                     -> index/
    3.4  Recherche hybride : fusion et reranking                -> retrieval/
    3.5  Construction du contexte et restitution ancrée         -> generation/
    3.6  Règle de citation littérale et garde-fous              -> generation/numeric, guardrails
    3.7  Prototype, deux modes et interface                     -> app/

Deux modes d'usage (Tableau A.1 du plan) :
    - MODE PRODUCTION   (amont)  : agents, corpus interne + publié.
    - MODE CONSULTATION (aval)   : décideurs, corpus publié uniquement.

Auteur : Adnane MAMA IDISSA — Master 2 MDSMS, ISSEA-CEMAC.
"""

from .config import Settings, Mode, DiffusionStatus, get_settings

__all__ = ["Settings", "Mode", "DiffusionStatus", "get_settings"]
__version__ = "1.0.0"
