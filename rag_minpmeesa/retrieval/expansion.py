"""
Expansion de requête par dictionnaire métier (démarche §4).

Contribution propre au terrain : le dictionnaire relie les sigles, les libellés
officiels et les formulations courantes du vocabulaire MINPMEESA (data/lexique/
synonymes.yaml). L'expansion enrichit la SEULE requête lexicale (jamais la
requête sémantique, jamais le contenu des passages), afin qu'une requête
« effectif des entreprises » atteigne, par la voie lexicale, un passage formulé
« nombre de PME ».

Elle est désactivable par config.yaml (expansion.enabled) pour permettre la
mesure de son apport par ablation (étape 7).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..index.text_utils import normalize, tokenize_fr


def load_lexique(path: Path) -> List[List[str]]:
    """Charge les familles de synonymes depuis un fichier YAML."""
    if not path.exists():
        return []
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    familles = data.get("familles", [])
    return [[str(t) for t in fam] for fam in familles if fam]


class QueryExpander:
    """Étend une requête lexicale à l'aide des familles de synonymes."""

    def __init__(self, familles: List[List[str]], max_expansions_per_term: int = 4):
        self.max = max_expansions_per_term
        # Pré-normalisation : (terme_normalisé, est_multi_mots) pour chaque membre.
        self._familles = []
        for fam in familles:
            membres = [(normalize(t.replace("_", " ")), t.replace("_", " ")) for t in fam]
            self._familles.append(membres)

    def expand(self, query: str) -> str:
        """Renvoie la requête enrichie des synonymes des familles déclenchées."""
        qn = normalize(query)
        q_tokens = set(tokenize_fr(query))
        ajouts: List[str] = []
        vus = set(q_tokens)
        for membres in self._familles:
            # La famille est déclenchée si l'un de ses membres apparaît dans la requête.
            declenchee = any(
                (norm in qn) if " " in norm else (norm in q_tokens)
                for norm, _ in membres
            )
            if not declenchee:
                continue
            n_ajoutes = 0
            for norm, _ in membres:
                for tok in norm.split():
                    if tok and tok not in vus:
                        vus.add(tok)
                        ajouts.append(tok)
                        n_ajoutes += 1
                if n_ajoutes >= self.max:
                    break
        if not ajouts:
            return query
        return query + " " + " ".join(ajouts)


def build_expander(settings) -> QueryExpander | None:
    """Construit l'expanseur d'après la configuration ; None si désactivé."""
    cfg = settings.expansion
    if not cfg.enabled:
        return None
    path = settings.paths.root / cfg.lexique_file
    familles = load_lexique(path)
    if not familles:
        return None
    return QueryExpander(familles, cfg.max_expansions_per_term)
