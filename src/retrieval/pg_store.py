"""
Dépôt PostgreSQL (cahier des charges, Étape 4a) — même interface que le dépôt
SQLite (src/retrieval/store.py), pour la machine cible du ministère.

Le filtrage temporel s'exprime dans la clause WHERE (exercice < N), avant tout
calcul : la même garantie que sur SQLite, vérifiable par un test qui échoue si un
passage postérieur remonte.

Nécessite psycopg2 (`pip install psycopg2-binary`). La connexion se fait par DSN
(chaîne de connexion) passée au constructeur ou via la variable d'environnement
RAG_PG_DSN, ex. « host=localhost dbname=minpmeesa user=postgres password=… ».
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .store import PassageRow, ValeurRow      # réutilise les mêmes structures


class PostgresStore:
    def __init__(self, dsn: Optional[str] = None):
        import psycopg2                         # import tardif (dépendance optionnelle)
        self._pg = psycopg2
        self.conn = psycopg2.connect(dsn or os.environ.get("RAG_PG_DSN", ""))
        self.conn.autocommit = False

    # ---- schéma --------------------------------------------------------- #
    def create_schema(self, schema_path: str = "db/schema_pg.sql") -> None:
        sql = Path(schema_path).read_text(encoding="utf-8")
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()

    def reset(self) -> None:
        """Vide les tables (réingestion reproductible)."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE passages, tableaux, appariement, documents RESTART IDENTITY;")
        self.conn.commit()

    # ---- écriture (mêmes signatures que Store) --------------------------- #
    def add_document(self, doc_id, type, exercice, periode="", source_file="", n_pages=0):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents(doc_id,type,exercice,periode,source_file,n_pages) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT (doc_id) DO UPDATE SET "
                "type=EXCLUDED.type, exercice=EXCLUDED.exercice",
                (doc_id, type, exercice, periode, source_file, n_pages))

    def add_passage(self, p: PassageRow):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO passages(doc_id,exercice,nature,code_indicateur,section,page,texte) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (p.doc_id, p.exercice, "commentaire", p.code_indicateur, p.section, p.page, p.texte))

    def add_valeur(self, v: ValeurRow):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tableaux(doc_id,exercice,tableau_n,page,ligne,colonne,valeur) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (v.doc_id, v.exercice, v.tableau_n, v.page, v.ligne, v.colonne, v.valeur))

    def add_appariement(self, code_indicateur, exercice, graphique_n, tableau_n, intitule=""):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO appariement(code_indicateur,exercice,graphique_n,tableau_n,intitule) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT (code_indicateur,exercice) DO UPDATE SET "
                "intitule=EXCLUDED.intitule",
                (code_indicateur, exercice, graphique_n, tableau_n, intitule))

    def commit(self):
        self.conn.commit()

    # ---- lecture (filtrage temporel dans le WHERE) ---------------------- #
    def commentaires_anterieurs(self, code_indicateur: str, exercice: int) -> List[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT exercice, texte, section FROM passages "
                "WHERE code_indicateur=%s AND exercice < %s ORDER BY exercice DESC",
                (code_indicateur, exercice))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def compter(self) -> dict:
        out = {}
        with self.conn.cursor() as cur:
            for t in ("documents", "passages", "tableaux", "appariement"):
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                out[t] = cur.fetchone()[0]
        return out
