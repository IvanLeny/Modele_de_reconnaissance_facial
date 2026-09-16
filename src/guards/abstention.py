"""
Abstention : le système sait ne pas répondre (cahier des charges, Étape 7.3).

Deux déclencheurs :
  1. **Univoque, sans paramètre** — absence de tableau apparié ou de valeurs pour
     l'exercice : sans données, aucun commentaire chiffré ne peut être fondé.
  2. **Faiblesse du contexte de référence** — l'appui documentaire (commentaires
     homologues antérieurs) est trop ténu. Mesuré par un score de confiance dont
     le seuil est CALIBRÉ (Étape 9), jamais choisi arbitrairement.

Le seuil vit dans config.yaml (aucune valeur en dur ici : `min_confiance` est un
paramètre, et sa valeur par défaut n'est qu'un point de départ documenté).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..guards.numeric import extract_numbers


@dataclass
class DecisionAbstention:
    abstention: bool
    motif: str
    confiance: float                  # score de confiance du contexte (0..1)


def confiance_contexte(commentaires_anterieurs: List[str]) -> float:
    """Score de confiance simple et monotone : fondé sur la quantité d'appui
    documentaire disponible (nombre de commentaires homologues et leur longueur).
    Borné à [0, 1]. Sert de variable à seuiller, calibrée à l'étape 9."""
    if not commentaires_anterieurs:
        return 0.0
    n = len(commentaires_anterieurs)
    longueur = sum(len(c.split()) for c in commentaires_anterieurs)
    # Saturation douce : 2 commentaires d'une trentaine de mots suffisent à
    # approcher 1. (Forme fixée ; le SEUIL de décision, lui, est calibré.)
    score = min(1.0, 0.5 * min(n, 2) / 2 + 0.5 * min(longueur, 60) / 60)
    return round(score, 4)


def decider(data_block: str,
            commentaires_anterieurs: List[str],
            min_confiance: float,
            tableau_apparie: bool = True) -> DecisionAbstention:
    """Décision d'abstention avant génération.

    - `data_block` : valeurs de l'exercice (vide ou sans nombre -> déclencheur 1).
    - `tableau_apparie` : faux si aucun tableau n'a pu être apparié (déclencheur 1).
    - `min_confiance` : seuil calibré (déclencheur 2).
    """
    if not tableau_apparie or not extract_numbers(data_block or ""):
        return DecisionAbstention(True, "aucun tableau apparié ou aucune valeur "
                                  "pour l'exercice", 0.0)
    conf = confiance_contexte(commentaires_anterieurs)
    if conf < min_confiance:
        return DecisionAbstention(True, f"contexte de référence trop faible "
                                  f"(confiance {conf:.2f} < seuil {min_confiance:.2f})", conf)
    return DecisionAbstention(False, "", conf)
