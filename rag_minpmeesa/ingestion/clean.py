"""
Nettoyage et normalisation du texte (chapitre 3.2).

Objectifs :
  - réparer les coupures de mots en fin de ligne (césures) ;
  - normaliser les espaces et les séparateurs, SANS toucher aux nombres ;
  - préserver strictement les valeurs chiffrées (espaces d'unités de mille,
    virgules décimales, symboles %, unités) car elles seront citées tel.

Aucune reformulation ni recomposition de nombre n'est effectuée : c'est une
exigence directe de la règle de citation littérale (3.6).
"""
from __future__ import annotations

import re

# Césure : "entre-\nprise" -> "entreprise"
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
# Espaces multiples (hors sauts de ligne)
_MULTISPACE = re.compile(r"[ \t ]+")
# Sauts de ligne multiples
_MULTINEWLINE = re.compile(r"\n{3,}")
# Puces et caractères décoratifs isolés
_BULLETS = re.compile(r"^[•▪◦●■❖–>\-\*]\s*", re.MULTILINE)
# Points de conduite des sommaires : "Titre ....... 6" -> "Titre 6"
_DOT_LEADERS = re.compile(r"\.{3,}")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _DOT_LEADERS.sub(" ", text)
    text = _BULLETS.sub("", text)
    # Normalise les espaces insécables des milliers vers un espace simple,
    # sans fusionner les chiffres (on conserve "1 234" -> "1 234").
    text = _MULTISPACE.sub(" ", text)
    text = _MULTINEWLINE.sub("\n\n", text)
    # Nettoie les espaces en fin de ligne
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()
