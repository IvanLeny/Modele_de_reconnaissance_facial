"""
Couche de stockage (cahier des charges, Étape 4a) — interface unique, deux
implémentations : SQLite (développement/tests, ici) et PostgreSQL+pgvector (sur
la machine cible). Le schéma logique est commun (voir db/schema.sql).

Point crucial (§4a, §5.1) : le **filtrage temporel s'exprime dans la clause
WHERE de la requête**, avant tout calcul de similarité. La méthode
`commentaires_anterieurs` n'accepte jamais un passage d'exercice ≥ N.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
    doc_id TEXT PRIMARY KEY, type TEXT, exercice INTEGER, periode TEXT,
    source_file TEXT, n_pages INTEGER, structure TEXT DEFAULT 'MINPMEESA/DEPP');
CREATE TABLE IF NOT EXISTS passages(
    id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, exercice INTEGER NOT NULL,
    nature TEXT, code_indicateur TEXT, section TEXT, page INTEGER, texte TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tableaux(
    id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, exercice INTEGER NOT NULL,
    tableau_n INTEGER, page INTEGER, ligne TEXT, colonne TEXT, valeur TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS appariement(
    code_indicateur TEXT, exercice INTEGER, graphique_n INTEGER, tableau_n INTEGER,
    intitule TEXT, PRIMARY KEY(code_indicateur, exercice));
CREATE INDEX IF NOT EXISTS idx_passages_ex ON passages(exercice);
CREATE INDEX IF NOT EXISTS idx_passages_code ON passages(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_tableaux_ex ON tableaux(exercice);
"""


@dataclass
class PassageRow:
    exercice: int
    code_indicateur: str
    texte: str
    doc_id: str = ""
    section: str = ""
    page: Optional[int] = None


@dataclass
class ValeurRow:
    exercice: int
    ligne: str
    colonne: str
    valeur: str
    doc_id: str = ""
    tableau_n: Optional[int] = None
    page: Optional[int] = None


class Store:
    """Dépôt SQLite. La même interface est réalisable sur PostgreSQL (psycopg)."""

    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SQLITE_SCHEMA)

    # ---- écriture ------------------------------------------------------- #
    def add_document(self, doc_id, type, exercice, periode="", source_file="", n_pages=0):
        self.conn.execute(
            "INSERT OR REPLACE INTO documents(doc_id,type,exercice,periode,source_file,n_pages)"
            " VALUES(?,?,?,?,?,?)", (doc_id, type, exercice, periode, source_file, n_pages))

    def add_passage(self, p: PassageRow):
        self.conn.execute(
            "INSERT INTO passages(doc_id,exercice,nature,code_indicateur,section,page,texte)"
            " VALUES(?,?,?,?,?,?,?)",
            (p.doc_id, p.exercice, "commentaire", p.code_indicateur, p.section, p.page, p.texte))

    def add_valeur(self, v: ValeurRow):
        self.conn.execute(
            "INSERT INTO tableaux(doc_id,exercice,tableau_n,page,ligne,colonne,valeur)"
            " VALUES(?,?,?,?,?,?,?)",
            (v.doc_id, v.exercice, v.tableau_n, v.page, v.ligne, v.colonne, v.valeur))

    def commit(self):
        self.conn.commit()

    # ---- lecture (filtrage temporel dans le WHERE) ---------------------- #
    def commentaires_anterieurs(self, code_indicateur: str, exercice: int) -> List[sqlite3.Row]:
        """Commentaires homologues des exercices STRICTEMENT antérieurs (§5.1)."""
        cur = self.conn.execute(
            "SELECT * FROM passages WHERE code_indicateur=? AND exercice < ? "
            "ORDER BY exercice DESC", (code_indicateur, exercice))
        return cur.fetchall()

    def valeurs_exercice(self, exercice: int, code_indicateur: Optional[str] = None) -> List[sqlite3.Row]:
        """Valeurs du tableau apparié pour l'exercice N (jamais postérieures)."""
        if code_indicateur is not None:
            cur = self.conn.execute(
                "SELECT t.* FROM tableaux t JOIN appariement a "
                "ON a.exercice=t.exercice AND a.tableau_n=t.tableau_n "
                "WHERE t.exercice=? AND a.code_indicateur=?", (exercice, code_indicateur))
        else:
            cur = self.conn.execute(
                "SELECT * FROM tableaux WHERE exercice=?", (exercice,))
        return cur.fetchall()

    def add_appariement(self, code_indicateur, exercice, graphique_n, tableau_n, intitule=""):
        self.conn.execute(
            "INSERT OR REPLACE INTO appariement VALUES(?,?,?,?,?)",
            (code_indicateur, exercice, graphique_n, tableau_n, intitule))

    def commentaires_similaires(self, intitule: str, exercice: int,
                                seuil: float = 0.4) -> List[sqlite3.Row]:
        """Commentaires des exercices ANTÉRIEURS dont l'indicateur a un intitulé
        proche (homologues), même si le code exact diffère d'une édition à
        l'autre. Filtrage temporel dans le WHERE (exercice < N)."""
        from .text import jaccard_tokens
        rows = self.conn.execute(
            "SELECT p.*, a.intitule AS intitule FROM passages p "
            "LEFT JOIN appariement a ON a.code_indicateur=p.code_indicateur "
            "AND a.exercice=p.exercice WHERE p.exercice < ? ORDER BY p.exercice DESC",
            (exercice,)).fetchall()
        out = []
        for r in rows:
            inti = r["intitule"] or ""
            if jaccard_tokens(intitule, inti) >= seuil:
                out.append(r)
        return out

    def valeurs_indicateur(self, exercice: int, intitule: str, limit: int = 40) -> List[sqlite3.Row]:
        """Valeurs de l'exercice dont les libellés (ligne/colonne) recoupent
        l'intitulé de l'indicateur. Filtrage par tokens (le lien exact
        valeur↔tableau n'étant pas toujours disponible, on cible par le sens)."""
        from .text import tokens
        cible = tokens(intitule)
        rows = self.conn.execute(
            "SELECT * FROM tableaux WHERE exercice=?", (exercice,)).fetchall()
        notes = []
        for r in rows:
            lib = tokens(f"{r['ligne']} {r['colonne']}")
            score = len(lib & cible) / len(lib | cible) if (lib or cible) else 0.0
            if score > 0:
                notes.append((score, r))
        notes.sort(key=lambda x: x[0], reverse=True)
        if notes:
            return [r for _, r in notes[:limit]]
        # Repli : si aucun libellé ne recoupe l'intitulé, on renvoie tout de même
        # les premières valeurs de l'exercice (le bloc de données existe bel et
        # bien — l'Annuaire de l'exercice —, l'abstention ne doit pas se déclencher
        # à tort au titre « aucune valeur »).
        return rows[:limit]
