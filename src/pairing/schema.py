"""
Structure de la table d'appariement + contrôles (cahier des charges, Étape 3).

Colonnes : code_indicateur, exercice, graphique_n, graphique_intitule,
tableau_n, tableau_intitule, score, statut.

Deux contrôles attendus par le cahier des charges :
  - **cohérence** : chaque code indicateur devrait apparaître dans au moins deux
    éditions (sans quoi il n'a pas d'homologue antérieur pour la génération) ;
  - **double saisie** : deux personnes remplissent indépendamment, on confronte
    et on calcule le taux d'accord (kappa de Cohen).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Tuple


def coherence_report(pairs: List) -> Dict:
    """Vérifie que chaque code indicateur a un homologue dans ≥ 2 éditions."""
    par_code: Dict[str, set] = defaultdict(set)
    for p in pairs:
        par_code[p.code_indicateur].add(p.exercice)
    multi = {c: sorted(ex) for c, ex in par_code.items() if len(ex) >= 2}
    solo = {c: sorted(ex) for c, ex in par_code.items() if len(ex) == 1}
    return {
        "n_codes": len(par_code),
        "n_codes_multi_editions": len(multi),
        "n_codes_une_edition": len(solo),
        "codes_multi_editions": multi,
    }


def cohen_kappa(saisie_a: Dict, saisie_b: Dict) -> Tuple[float, int, int]:
    """Kappa de Cohen entre deux saisies indépendantes de l'appariement.

    `saisie_a` / `saisie_b` : dict {(exercice, graphique_n) -> tableau_n choisi}.
    Renvoie (kappa, n_communs, n_accords). Accord = même tableau choisi.
    """
    cles = set(saisie_a) & set(saisie_b)
    n = len(cles)
    if n == 0:
        return 0.0, 0, 0
    accords = sum(1 for k in cles if saisie_a[k] == saisie_b[k])
    p_o = accords / n
    # Accord attendu par hasard, à partir des distributions marginales des choix.
    ca = Counter(saisie_a[k] for k in cles)
    cb = Counter(saisie_b[k] for k in cles)
    p_e = sum((ca[v] / n) * (cb[v] / n) for v in set(ca) | set(cb))
    kappa = 1.0 if p_e == 1.0 else (p_o - p_e) / (1 - p_e)
    return round(kappa, 4), n, accords
