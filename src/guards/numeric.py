"""
Contrôle de citation littérale des valeurs (cahier des charges, Étape 7.1).

C'est LE garde-fou central : il rend l'exactitude numérique une propriété du
dispositif, indépendante du modèle. Il opère APRÈS la génération, sur le texte
produit, et n'a besoin que de deux entrées :
  - les propositions produites (chaque proposition = une affirmation vérifiable) ;
  - le **bloc de données** de l'exercice traité (valeurs autorisées).

Quatre règles (cahier des charges) :
  1. Normalisation préalable — séparateurs de milliers, espaces insécables et
     marques décimales harmonisés avant toute comparaison.
  2. Exclusion des millésimes isolés (20XX) — ce sont des repères temporels, pas
     des données à contrôler.
  3. Interdiction du recalcul — le contrôle porte sur la valeur telle qu'elle est
     écrite ; aucune valeur dérivée n'est acceptée, même si elle est exacte.
  4. Portée de la source — la valeur doit figurer dans le bloc de données de
     l'exercice, **jamais** dans les commentaires antérieurs (motif : révision
     des estimations d'une édition à l'autre).

Une valeur non appariée entraîne le retrait de la proposition qui la porte et un
signalement visible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# Un nombre : chiffres avec séparateurs de milliers/décimaux éventuels et signe %.
_NUMBER_RE = re.compile(r"-?\d[\d   .,]*\d|\d")
_YEAR_RE = re.compile(r"^20\d{2}$")


def normalize_number(token: str) -> str:
    """Règle 1 : forme canonique d'une valeur pour comparaison.

    Retire espaces (normaux, insécables, fins) servant de séparateurs de
    milliers ; unifie la marque décimale sur la virgule ; retire un éventuel
    signe %/pourcent traité séparément. « 393 954 » et « 393954 » deviennent
    identiques ; « 79.6 » et « 79,6 » aussi.
    """
    t = token.strip().lower()
    t = t.replace("%", "").strip()
    t = t.replace(" ", "").replace(" ", "").replace(" ", "")
    # Si le token a à la fois '.' et ',' -> le dernier est la décimale.
    if "." in t and "," in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "")            # points = milliers
        else:
            t = t.replace(",", "")            # virgules = milliers
    t = t.replace(".", ",")                   # marque décimale unifiée sur ','
    # Retire des zéros décimaux non significatifs pour comparer 0,10 et 0,1 ? NON :
    # règle 3 (pas de recalcul) -> on compare littéralement, sans normaliser la
    # précision. On conserve donc la forme telle quelle après unification.
    return t


def extract_numbers(text: str) -> List[str]:
    """Tous les nombres d'un texte, millésimes isolés exclus (règle 2)."""
    out = []
    for m in _NUMBER_RE.findall(text):
        canon = normalize_number(m)
        if not canon:
            continue
        if _YEAR_RE.match(canon.replace(",", "")):
            continue                          # millésime isolé -> ignoré
        out.append(canon)
    return out


def _authorized_set(data_block: str) -> set:
    """Ensemble des valeurs autorisées, normalisées, issues du SEUL bloc de
    données (règle 4). Les commentaires antérieurs ne sont jamais passés ici."""
    return set(extract_numbers(data_block))


def number_supported(number_token: str, data_block: str) -> bool:
    """Une valeur est soutenue si sa forme canonique figure littéralement dans le
    bloc de données (aucune valeur dérivée acceptée — règle 3)."""
    canon = normalize_number(number_token)
    if _YEAR_RE.match(canon.replace(",", "")):
        return True                           # un millésime n'est pas contrôlé
    return canon in _authorized_set(data_block)


@dataclass
class Proposition:
    """Affirmation vérifiable indépendamment, issue de la génération."""
    texte: str
    source_id: str = ""                       # identifiant du passage d'origine


@dataclass
class AuditProposition:
    proposition: Proposition
    valeurs: List[str] = field(default_factory=list)
    valeurs_non_soutenues: List[str] = field(default_factory=list)

    @property
    def retenue(self) -> bool:
        return not self.valeurs_non_soutenues


@dataclass
class AuditNumerique:
    retenues: List[AuditProposition] = field(default_factory=list)
    ecartees: List[AuditProposition] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.retenues) + len(self.ecartees)

    @property
    def n_valeurs(self) -> int:
        return sum(len(a.valeurs) for a in self.retenues + self.ecartees)

    @property
    def n_valeurs_appariees(self) -> int:
        return sum(len(a.valeurs) - len(a.valeurs_non_soutenues)
                   for a in self.retenues + self.ecartees)

    @property
    def exactitude(self) -> float:
        """Part des valeurs citées effectivement présentes dans le bloc de
        données (borne théorique 1 ; > 1 signalerait une erreur de définition)."""
        return 1.0 if self.n_valeurs == 0 else self.n_valeurs_appariees / self.n_valeurs

    def to_dict(self) -> dict:
        return {
            "n_propositions": self.total,
            "n_retenues": len(self.retenues),
            "n_ecartees": len(self.ecartees),
            "n_valeurs": self.n_valeurs,
            "n_valeurs_appariees": self.n_valeurs_appariees,
            "exactitude": round(self.exactitude, 4),
            "propositions_ecartees": [
                {"texte": a.proposition.texte,
                 "valeurs_non_soutenues": a.valeurs_non_soutenues}
                for a in self.ecartees
            ],
        }


def controler_propositions(propositions: List[Proposition], data_block: str) -> AuditNumerique:
    """Applique le contrôle de citation littérale à une liste de propositions.

    Le `data_block` est le SEUL contexte autorisé pour les valeurs (règle 4) :
    n'y passez jamais les commentaires antérieurs.
    """
    audit = AuditNumerique()
    for prop in propositions:
        vals = extract_numbers(prop.texte)
        non_ok = [v for v in vals if not number_supported(v, data_block)]
        a = AuditProposition(proposition=prop, valeurs=vals, valeurs_non_soutenues=non_ok)
        (audit.retenues if a.retenue else audit.ecartees).append(a)
    return audit
