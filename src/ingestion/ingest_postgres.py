"""
Peuplement de la base PostgreSQL (cahier des charges, Étape 4a).

Crée le schéma, ingère le corpus dans PostgreSQL, puis VÉRIFIE le critère
d'acceptation : le filtrage temporel (WHERE exercice < N) n'autorise aucun
passage postérieur. Affiche enfin les compteurs (persistance vérifiable en
rouvrant la base).

Usage (Windows, Anaconda Prompt) :
    set RAG_PG_DSN=host=localhost dbname=minpmeesa user=postgres password=VOTRE_MDP
    python -m src.ingestion.ingest_postgres
"""
from __future__ import annotations

import os
import sys

from .ingest import populate
from ..retrieval.pg_store import PostgresStore


def main() -> int:
    dsn = os.environ.get("RAG_PG_DSN", "")
    if not dsn:
        print("Définissez RAG_PG_DSN, ex. :\n"
              '  set RAG_PG_DSN=host=localhost dbname=minpmeesa user=postgres password=VOTRE_MDP')
        return 2
    try:
        store = PostgresStore(dsn)
    except Exception as e:
        print(f"Connexion PostgreSQL impossible : {type(e).__name__} : {e}")
        return 1

    print("1/4  Création du schéma (db/schema_pg.sql)…")
    store.create_schema()
    print("2/4  Réinitialisation des tables…")
    store.reset()
    print("3/4  Ingestion du corpus dans PostgreSQL…")
    populate(store, verbose=True)

    print("4/4  Vérification du filtrage temporel (aucun passage postérieur)…")
    ok = True
    with store.conn.cursor() as cur:
        cur.execute("SELECT DISTINCT code_indicateur FROM passages LIMIT 200")
        codes = [r[0] for r in cur.fetchall()]
    for code in codes:
        for n in (2022, 2023, 2024):
            for r in store.commentaires_anterieurs(code, n):
                if r["exercice"] >= n:
                    ok = False
                    print(f"   ÉCHEC : passage exercice {r['exercice']} remonté pour N={n}")
    print("   OK — le filtrage temporel exclut tout exercice ≥ N."
          if ok else "   ÉCHEC du filtrage temporel.")

    counts = store.compter()
    print("\nContenu de la base :")
    for t, n in counts.items():
        print(f"   {t:12} : {n}")
    print("\nPersistance : rouvrez la base (psql) — les données subsistent après "
          "l'arrêt de l'application.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
