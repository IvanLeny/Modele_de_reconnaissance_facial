"""
Ajout d'un document à la base PostgreSQL (maintenance, §3.1.5).

Permet au ministère d'enrichir la base à l'avenir avec un nouveau PDF (annuaire,
rapport d'analyse, note de conjoncture, document de contexte), sans réingérer
tout le corpus. Le type et l'exercice sont détectés à partir du contenu.

Usage (Windows) :
    set RAG_PG_DSN=host=localhost dbname=minpmeesa user=postgres password=VOTRE_MDP
    python -m src.ingestion.add_document "chemin\\vers\\nouveau_document.pdf"
"""
from __future__ import annotations

import os
import sys

from .ingest import ingest_document
from ..retrieval.pg_store import PostgresStore


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print('Usage : python -m src.ingestion.add_document "chemin\\vers\\document.pdf"')
        return 2
    pdf = argv[0]
    if not os.path.exists(pdf):
        print(f"Fichier introuvable : {pdf}")
        return 2
    dsn = os.environ.get("RAG_PG_DSN", "")
    if not dsn:
        print("Définissez RAG_PG_DSN (voir docs/INSTALLATION_NOUVEAU.md).")
        return 2
    try:
        store = PostgresStore(dsn)
        store.create_schema()          # idempotent : ne recrée pas si présent
    except Exception as e:
        print(f"Connexion PostgreSQL impossible : {type(e).__name__} : {e}")
        return 1

    print(f"Ingestion de {pdf} …")
    added = ingest_document(store, pdf, verbose=True)
    print(f"\nDocument ajouté : {added['doc_id']} "
          f"(type={added['type']}, exercice={added['exercice']}, "
          f"périodicité={added['periode'] or '—'})")
    print(f"  + {added['valeurs']} valeurs, + {added['passages']} passages.")
    print("\nContenu de la base :")
    for t, n in store.compter().items():
        print(f"   {t:12} : {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
