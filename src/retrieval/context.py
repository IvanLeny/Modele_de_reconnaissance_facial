"""
Assemblage du contexte de génération (cahier des charges, Étape 5.3).

Le contexte est constitué de **trois blocs distincts et étiquetés**, jamais
mélangés (c'est ce qui permet au garde-fou numérique de n'autoriser que les
valeurs de l'exercice traité) :

  1. VALEURS DE L'EXERCICE N — les seules valeurs citables (bloc de données) ;
  2. VALEURS ANTÉRIEURES — pour situer une évolution, non citables littéralement ;
  3. COMMENTAIRES ANTÉRIEURS — le « patron » de rédaction (forme, pas valeurs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .store import Store


@dataclass
class Contexte:
    exercice: int
    code_indicateur: str
    valeurs_n: List[str] = field(default_factory=list)          # énoncés « ligne | colonne = valeur »
    valeurs_anterieures: List[str] = field(default_factory=list)
    commentaires_anterieurs: List[str] = field(default_factory=list)

    def bloc_donnees(self) -> str:
        """Bloc de données de l'exercice N — SEUL contexte passé au garde-fou
        numérique (portée de la source, règle 4)."""
        return "\n".join(self.valeurs_n)

    def rendu(self) -> str:
        """Rendu étiqueté des trois blocs, pour l'instruction de génération."""
        parts = ["### VALEURS DE L'EXERCICE " + str(self.exercice) + " (seules citables)"]
        parts += self.valeurs_n or ["(aucune)"]
        parts.append("\n### VALEURS ANTÉRIEURES (contexte, non citables)")
        parts += self.valeurs_anterieures or ["(aucune)"]
        parts.append("\n### COMMENTAIRES ANTÉRIEURS (modèle de rédaction, ne pas reprendre les valeurs)")
        parts += self.commentaires_anterieurs or ["(aucun)"]
        return "\n".join(parts)


def _valeurs_texte(rows) -> List[str]:
    out = []
    for r in rows:
        ligne, colonne, valeur = r["ligne"], r["colonne"], r["valeur"]
        col = f" | {colonne}" if colonne else ""
        out.append(f"{ligne}{col} = {valeur}")
    return out


def assembler_contexte(store: Store, code_indicateur: str, exercice: int,
                       intitule: str = "", max_valeurs: int = 60,
                       max_commentaires: int = 4) -> Contexte:
    """Assemble le contexte pour (code indicateur, exercice N). Le filtrage
    temporel est réalisé par les requêtes du dépôt (clause WHERE).

    Si `intitule` est fourni, les valeurs sont ciblées par recoupement de sens
    (valeurs_indicateur) ; sinon par l'appariement code→tableau (valeurs_exercice).
    """
    ctx = Contexte(exercice=exercice, code_indicateur=code_indicateur)

    if intitule:
        vals_n = store.valeurs_indicateur(exercice, intitule)
        ant = []
        for ex in range(exercice - 1, exercice - 4, -1):
            ant += store.valeurs_indicateur(ex, intitule)
    else:
        vals_n = store.valeurs_exercice(exercice, code_indicateur)
        ant = []
        for ex in range(exercice - 1, exercice - 4, -1):
            ant += store.valeurs_exercice(ex, code_indicateur)
    ctx.valeurs_n = _valeurs_texte(vals_n)[:max_valeurs]
    ctx.valeurs_anterieures = _valeurs_texte(ant)[:max_valeurs]

    # Homologues antérieurs : par code exact, complété par similarité d'intitulé
    # (le code peut varier légèrement d'une édition à l'autre).
    coms = list(store.commentaires_anterieurs(code_indicateur, exercice))
    if intitule:
        vus = {c["texte"] for c in coms}
        for c in store.commentaires_similaires(intitule, exercice):
            if c["texte"] not in vus:
                coms.append(c)
    ctx.commentaires_anterieurs = [c["texte"] for c in coms][:max_commentaires]
    return ctx
