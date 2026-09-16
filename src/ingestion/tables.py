"""
Détection et linéarisation des tableaux (cahier des charges, Étape 2).

Objectif central : conserver la **correspondance entre chaque valeur et ses
en-têtes de ligne et de colonne**. Un tableau de répartition par secteur et par
exercice doit produire des énoncés élémentaires du type
« Primaire | 2016 · Effectif = 342 », et non une matrice de nombres.

Traite :
  - les en-têtes sur plusieurs niveaux (une colonne portant un exercice ET une
    unité) par remplissage horizontal des cellules fusionnées puis composition
    du chemin de colonne ;
  - les tableaux scindés entre deux pages par report de l'en-tête (au niveau de
    l'appelant, via `linearize_document`).

S'appuie sur la détection de tableaux de PyMuPDF (`page.find_tables`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import pymupdf

_NUM = re.compile(r"\d")


@dataclass
class Cellule:
    """Une valeur élémentaire reliée à ses libellés (Étape 2.1)."""
    ligne: str                      # libellé de ligne (ex. « Primaire »)
    colonne: str                    # chemin de colonne (ex. « 2016 · Effectif »)
    valeur: str                     # valeur telle qu'écrite (ex. « 342 » ou « 0,17 »)

    def enonce(self) -> str:
        col = f" | {self.colonne}" if self.colonne else ""
        return f"{self.ligne}{col} = {self.valeur}"


@dataclass
class Tableau:
    page: int
    n_lignes: int
    n_colonnes: int
    cellules: List[Cellule] = field(default_factory=list)
    titre: str = ""

    def texte_linearise(self) -> str:
        tete = f"{self.titre}\n" if self.titre else ""
        return tete + "\n".join(c.enonce() for c in self.cellules)


def _clean(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.replace("\n", " ")).strip()


def _is_numeric(s: str) -> bool:
    """Vraie valeur chiffrée (au moins un chiffre, pas seulement de la ponctuation)."""
    return bool(_NUM.search(s))


_YEAR = re.compile(r"\b20\d{2}\b")


def _is_data_value(s: str) -> bool:
    """Valeur de donnée : chiffrée mais PAS un simple millésime (20XX), qui est un
    en-tête temporel (ex. « 2016 », « 2023 (e) »)."""
    s = s.strip()
    if not _is_numeric(s):
        return False
    # « 2016 », « 2023 (e) » -> en-tête ; « 342 », « 0,17 », « 79,6 % » -> donnée.
    return not _YEAR.fullmatch(re.sub(r"\s*\(e\)\s*", "", s).strip())


def _header_depth(rows: List[List[str]]) -> int:
    """Nombre de lignes d'en-tête : les premières lignes dont la 1re cellule est
    vide ou non chiffrée et qui ne constituent pas encore une ligne de données."""
    depth = 0
    for r in rows:
        first = _clean(r[0]) if r else ""
        rest = [_clean(c) for c in r[1:]]
        # Une ligne de données a un libellé de ligne non vide ET au moins une
        # vraie valeur (les millésimes en en-tête ne comptent pas comme données).
        if first and any(_is_data_value(c) for c in rest):
            break
        depth += 1
        if depth >= 3:                 # au plus trois niveaux d'en-tête
            break
    return max(depth, 1)


def _ffill(row: List[str]) -> List[str]:
    """Remplit horizontalement les cellules vides par la dernière valeur vue
    (cellules d'en-tête fusionnées : « 2016 » couvre « Effectif » et « % »)."""
    out, last = [], ""
    for c in row:
        c = _clean(c)
        if c:
            last = c
        out.append(last)
    return out


def linearize_table(rows: List[List[str]], page: int, titre: str = "") -> Tableau:
    rows = [[_clean(c) for c in r] for r in rows if any(_clean(c) for c in r)]
    if not rows:
        return Tableau(page=page, n_lignes=0, n_colonnes=0, titre=titre)
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]

    depth = _header_depth(rows)
    header_rows = [_ffill(r) for r in rows[:depth]]
    data_rows = rows[depth:]

    # Chemin de colonne = composition des niveaux d'en-tête (dédupliqué).
    col_paths: List[str] = []
    for j in range(ncol):
        parts, seen = [], set()
        for hr in header_rows:
            v = hr[j] if j < len(hr) else ""
            if v and v not in seen:
                seen.add(v)
                parts.append(v)
        col_paths.append(" · ".join(parts))

    cells: List[Cellule] = []
    for r in data_rows:
        libelle = r[0]
        if not libelle:
            continue
        for j in range(1, ncol):
            val = r[j]
            if val and _is_data_value(val):
                cells.append(Cellule(ligne=libelle, colonne=col_paths[j], valeur=val))
    return Tableau(page=page, n_lignes=len(data_rows), n_colonnes=ncol,
                   cellules=cells, titre=titre)


def extract_tables(pdf_path: str) -> List[Tableau]:
    """Extrait et linéarise tous les tableaux exploitables d'un PDF."""
    doc = pymupdf.open(pdf_path)
    out: List[Tableau] = []
    for i, page in enumerate(doc, start=1):
        try:
            found = page.find_tables()
        except Exception:
            continue
        for t in found.tables:
            rows = t.extract()
            lin = linearize_table(rows, page=i)
            if lin.cellules:              # on ne garde que les tableaux porteurs de valeurs
                out.append(lin)
    doc.close()
    return out
