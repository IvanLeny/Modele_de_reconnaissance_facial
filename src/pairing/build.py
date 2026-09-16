"""
Aide à la construction de la table d'appariement (cahier des charges, Étape 3).

L'appariement relie chaque **graphique commenté** d'un Rapport d'analyse au
**tableau** de l'Annuaire du même exercice qui en porte les valeurs, avec un
**code indicateur stable d'une édition à l'autre**. Il rend possible la
récupération ciblée (Étape 5).

Le cahier des charges est explicite : la construction finale se fait **à la
main**, par correspondance des intitulés, avec double saisie et calcul du taux
d'accord. Le rôle de ce module est donc de **préparer le fichier de travail** :
extraire les intitulés, proposer des appariements candidats par similarité, et
attribuer un code indicateur stable — jamais de trancher seul.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..ingestion.extract import extract_document
from ..retrieval.text import jaccard_tokens, tokens

# Années et mentions d'unité à retirer pour rendre un code indicateur stable
# d'une édition à l'autre (« … en 2023 … (en %) » -> même code que 2024).
_YEAR = re.compile(r"\b20\d{2}\b")
_PARENS = re.compile(r"\([^)]*\)")


@dataclass
class Item:
    numero: int
    intitule: str


@dataclass
class Appariement:
    code_indicateur: str
    exercice: int
    graphique_n: int
    graphique_intitule: str
    tableau_n: Optional[int]
    tableau_intitule: str
    score: float
    statut: str = "candidat"          # candidat -> à valider/corriger à la main


def _clean_intitule(s: str) -> str:
    s = re.sub(r"\.{2,}.*$", "", s)          # points de conduite + n° de page
    s = re.sub(r"\s+\d+\s*$", "", s)          # numéro de page résiduel
    return re.sub(r"\s+", " ", s).strip(" .")


def _extract_items(path: str, mot: str) -> List[Item]:
    ft = extract_document(path).full_text()
    seen: Dict[int, str] = {}
    for m in re.finditer(mot + r"\s+(\d+)\s*[:.\-–]\s*([^\n]{4,140})", ft, re.I):
        n = int(m.group(1))
        lib = _clean_intitule(m.group(2))
        if n not in seen and len(lib) >= 4:
            seen[n] = lib
    return [Item(n, seen[n]) for n in sorted(seen)]


def extract_graphiques(rapport_path: str) -> List[Item]:
    return _extract_items(rapport_path, "Graphique")


def extract_tableaux(annuaire_path: str) -> List[Item]:
    return _extract_items(annuaire_path, "Tableau")


def code_indicateur(intitule: str) -> str:
    """Code stable dérivé de l'intitulé, débarrassé de l'année et des unités."""
    s = _PARENS.sub(" ", intitule)
    s = _YEAR.sub(" ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    toks = [t for t in tokens(s)]
    toks = sorted(set(toks))                  # ordre indifférent -> stabilité
    return "-".join(toks[:6]) if toks else "indicateur"


def _best_table(graph: Item, tables: List[Item]) -> Tuple[Optional[Item], float]:
    best, best_s = None, 0.0
    for t in tables:
        s = jaccard_tokens(graph.intitule, t.intitule)
        if s > best_s:
            best_s, best = s, t
    return best, round(best_s, 3)


def build_pairs(exercice: int, rapport_path: str, annuaire_path: str) -> List[Appariement]:
    graphs = extract_graphiques(rapport_path)
    tables = extract_tableaux(annuaire_path)
    out: List[Appariement] = []
    for g in graphs:
        t, s = _best_table(g, tables)
        out.append(Appariement(
            code_indicateur=code_indicateur(g.intitule),
            exercice=exercice,
            graphique_n=g.numero, graphique_intitule=g.intitule,
            tableau_n=(t.numero if t else None),
            tableau_intitule=(t.intitule if t else ""),
            score=s,
            statut="candidat" if s >= 0.30 else "à_vérifier",
        ))
    return out


_FIELDS = ["code_indicateur", "exercice", "graphique_n", "graphique_intitule",
           "tableau_n", "tableau_intitule", "score", "statut"]


def write_pairs(pairs: List[Appariement], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS, delimiter=";")
        w.writeheader()
        for p in pairs:
            w.writerow({k: getattr(p, k) for k in _FIELDS})
    return out_path
