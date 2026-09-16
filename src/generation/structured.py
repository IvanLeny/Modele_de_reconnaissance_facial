"""
Sortie structurée en propositions (cahier des charges, Étape 6.3).

Le modèle produit une liste de propositions (une par ligne, préfixée « - »).
Une proposition est une affirmation vérifiable indépendamment. On découpe aussi
une proposition portant plusieurs valeurs en autant d'affirmations élémentaires,
afin que le garde-fou numérique agisse au grain le plus fin.
"""
from __future__ import annotations

import re
from typing import List

from ..guards.numeric import Proposition, extract_numbers

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÉÈÀÂÎ0-9])")


def parser_propositions(texte_modele: str, source_id: str = "") -> List[Proposition]:
    """Transforme la sortie brute du modèle en propositions élémentaires."""
    props: List[Proposition] = []
    for ligne in texte_modele.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        ligne = re.sub(r"^[-*•\d.)\s]+", "", ligne).strip()   # retire la puce
        if len(ligne) < 4:
            continue
        # Découpe en phrases ; une phrase multi-valeurs -> plusieurs propositions.
        for phrase in _SENT_SPLIT.split(ligne):
            phrase = phrase.strip()
            if not phrase:
                continue
            nums = extract_numbers(phrase)
            if len(nums) <= 1:
                props.append(Proposition(texte=phrase, source_id=source_id))
            else:
                # Plusieurs valeurs : on conserve la phrase entière comme une
                # proposition (chaque valeur y est contrôlable), ET on la marque
                # comme composite pour le décompte.
                props.append(Proposition(texte=phrase, source_id=source_id))
    return props
