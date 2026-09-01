"""
Traitement contrôlé des données chiffrées (chapitre 3.6) — cœur du dispositif.

La règle de conception centrale du mémoire (plan A.2) : toute donnée chiffrée
restituée doit être reprise LITTÉRALEMENT d'un passage source, sans reformulation,
sans recalcul et sans arrondi, et accompagnée de sa référence. Ce module :

  1. extrait les mentions numériques d'un texte (français : « 1 234,5 », « 12,3 % »,
     « 45 000 FCFA », millésimes, plages…) ;
  2. vérifie qu'une donnée chiffrée d'une réponse figure TELLE QUELLE dans au
     moins un passage source cité (audit numérique) ;
  3. signale toute donnée non appariée — la fragilité principale d'un système
     génératif sur corpus statistique (hallucination numérique).

L'audit numérique alimente à la fois le garde-fou de restitution (on refuse de
présenter un chiffre non sourcé) et la métrique d'exactitude chiffrée du
chapitre 4 (critère de validation de H3 : exactitude > 0,95).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional


# Un nombre français : chiffres avec séparateurs de milliers (espace normal ou
# insécable) et décimale virgule ou point ; capté avec un éventuel symbole %.
_NUMBER_RE = re.compile(
    r"""
    (?<![\w.,])                     # pas collé à une lettre/chiffre précédent
    \d{1,3}(?:[    ]\d{3})+(?:[.,]\d+)?   # 1 234 / 1 234,5
    | \d+(?:[.,]\d+)?               # 12 / 12,3 / 12.3
    """,
    re.VERBOSE,
)
_PERCENT_SUFFIX = re.compile(r"^\s*(%|pour\s*cent|p\.?\s*100)", re.IGNORECASE)


def _norm_space(s: str) -> str:
    """Uniformise les espaces (insécables -> normal) pour la comparaison."""
    s = s.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class NumberMention:
    raw: str                 # texte exact tel qu'il apparaît (pour citation littérale)
    canonical: str           # forme normalisée (espaces uniformisés) pour l'appariement
    is_percent: bool = False
    start: int = 0
    end: int = 0

    def __repr__(self):
        return f"<Num {self.raw!r}{'%' if self.is_percent else ''}>"


def extract_numbers(text: str) -> List[NumberMention]:
    """Extrait toutes les mentions numériques d'un texte."""
    mentions: List[NumberMention] = []
    for m in _NUMBER_RE.finditer(text):
        raw = m.group(0)
        tail = text[m.end():m.end() + 8]
        is_percent = bool(_PERCENT_SUFFIX.match(tail))
        mentions.append(NumberMention(
            raw=raw,
            canonical=_norm_space(raw),
            is_percent=is_percent,
            start=m.start(),
            end=m.end(),
        ))
    return mentions


def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s)


def number_supported(mention: NumberMention, source_texts: List[str]) -> bool:
    """
    Vrai si le nombre figure littéralement dans une source.

    L'appariement est d'abord littéral (forme canonique, espaces uniformisés),
    puis, par sécurité, sur la suite de chiffres seule — de sorte qu'un même
    nombre écrit « 1 234 » ou « 1234 » soit reconnu, SANS jamais tolérer une
    valeur différente (ni arrondi ni recalcul).
    """
    canon = mention.canonical
    digits = _digits_only(canon)
    for src in source_texts:
        src_norm = _norm_space(src)
        if canon and canon in src_norm:
            return True
        # Repli : mêmes chiffres exacts présents dans une mention de la source.
        if digits:
            for sm in extract_numbers(src_norm):
                if _digits_only(sm.canonical) == digits:
                    return True
    return False


@dataclass
class NumericAudit:
    total: int = 0
    supported: int = 0
    unsupported: List[str] = field(default_factory=list)  # formes brutes non sourcées

    @property
    def accuracy(self) -> float:
        """Exactitude chiffrée : part des nombres restitués effectivement sourcés."""
        return 1.0 if self.total == 0 else self.supported / self.total

    @property
    def all_supported(self) -> bool:
        return not self.unsupported

    def to_dict(self) -> dict:
        return {"total": self.total, "supported": self.supported,
                "unsupported": self.unsupported, "accuracy": round(self.accuracy, 4)}


_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def is_meaningful_figure(mention: NumberMention) -> bool:
    """
    Vrai si la mention est une STATISTIQUE exploitable et non un simple repère :
      - un pourcentage (69,80 %) ou une décimale (5,7) ;
      - un grand entier (>= 3 chiffres, ex. 393 166) ;
    et FAUX pour un ordinal isolé (1, 2, 5) ou un millésime seul (2023).
    """
    canon = mention.canonical
    if mention.is_percent or re.search(r"\d[.,]\d", canon):
        return True
    digits = re.sub(r"\D", "", canon)
    if len(digits) >= 3:
        if len(digits) == 4 and _YEAR_RE.match(digits):   # millésime seul
            return False
        return True
    return False


def key_figures(text: str) -> List[str]:
    """
    Extrait les chiffres-clés lisibles d'un texte, dédoublonnés et suffixés du
    symbole « % » lorsqu'il s'applique. Destiné à la colonne « Données chiffrées »
    de la fiche de collecte : on ne garde que ce qui est réellement exploitable.
    """
    out, seen = [], set()
    for m in extract_numbers(text):
        if not is_meaningful_figure(m):
            continue
        label = m.raw + (" %" if m.is_percent else "")
        key = re.sub(r"\s+", "", label)
        if key not in seen:
            seen.add(key)
            out.append(label)
    return out


def audit_numbers(answer_text: str, source_texts: List[str]) -> NumericAudit:
    """Audite tous les nombres d'une réponse au regard des passages sources."""
    audit = NumericAudit()
    for mention in extract_numbers(answer_text):
        audit.total += 1
        if number_supported(mention, source_texts):
            audit.supported += 1
        else:
            audit.unsupported.append(mention.raw)
    return audit
