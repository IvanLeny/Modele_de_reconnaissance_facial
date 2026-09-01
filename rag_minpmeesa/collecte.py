"""
Aide à la collecte d'informations pour l'Annuaire statistique (chapitre 3.7).

Le premier usage du système (mode production) est d'aider les agents à RÉUNIR,
depuis les documents sources, les informations à transcrire dans l'Annuaire. Ce
module organise cette collecte par RUBRIQUES calquées sur la structure de
l'Annuaire des PMEESA. Pour chaque rubrique, il interroge le système, récupère
les passages pertinents et en extrait les données chiffrées AVEC leur référence
— exactement ce qu'un rédacteur doit reporter, sans avoir à ressaisir un chiffre.

Le résultat est directement exportable (CSV / Markdown) pour préparer les
tableaux de l'Annuaire.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .config import Mode
from .generation.numeric import key_figures


# Rubriques de l'Annuaire statistique des PMEESA et requêtes associées.
# (Chaque rubrique déclenche une ou plusieurs interrogations du corpus.)
RUBRIQUES: Dict[str, List[str]] = {
    "Stock et structure des PME": [
        "nombre d'entreprises et de PME estimé en 2023",
        "répartition du stock des PME par secteur d'activité",
        "répartition du stock des PME par région",
    ],
    "Création des PME (CFCE)": [
        "nombre de PME créées dans les CFCE",
        "création de PME par type d'entreprise et par région",
    ],
    "Emploi dans les PME": [
        "emplois créés par les PME",
        "situation de l'emploi dans les PME par branche d'activité",
    ],
    "Contribution économique et valeur ajoutée": [
        "contribution des PME à l'économie et valeur ajoutée",
        "évolution de la valeur ajoutée des PME",
    ],
    "Trésorerie et financement": [
        "situation de la trésorerie des PME",
        "sources de financement des investissements des PME",
    ],
    "Conjoncture : activité et coûts de production": [
        "évolution du niveau d'activité des PME",
        "perception des coûts de production des PME",
    ],
    "Inflation et prix": [
        "taux d'inflation au Cameroun",
        "évolution des prix à la production industrielle",
    ],
    "Politiques publiques et appui aux PME": [
        "mesures d'appui et d'accompagnement des PME",
        "programmes et services en faveur des PME",
    ],
}


@dataclass
class Finding:
    rubrique: str
    query: str
    sentence: str
    citation: str
    doc_id: str
    numbers: List[str] = field(default_factory=list)


def collect_rubrique(engine, rubrique: str, mode: Mode = Mode.PRODUCTION,
                     max_per_query: int = 3) -> List[Finding]:
    """Réunit les constats sourcés d'une rubrique (phrases + chiffres + référence)."""
    findings: List[Finding] = []
    seen = set()
    for query in RUBRIQUES.get(rubrique, []):
        ans = engine.query(query, mode=mode)
        if ans.refused:
            continue
        n = 0
        for s in ans.sentences:
            nums = key_figures(s.text)
            # On ne retient, pour la collecte, que les constats effectivement
            # porteurs d'une donnée chiffrée exploitable.
            if not nums:
                continue
            key = s.text[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(
                rubrique=rubrique, query=query, sentence=s.text,
                citation=s.citation, doc_id=s.sid, numbers=nums,
            ))
            n += 1
            if n >= max_per_query:
                break
    return findings


def collect_all(engine, mode: Mode = Mode.PRODUCTION) -> List[Finding]:
    out: List[Finding] = []
    for rubrique in RUBRIQUES:
        out.extend(collect_rubrique(engine, rubrique, mode=mode))
    return out


def findings_to_markdown(findings: List[Finding]) -> str:
    lines = ["# Fiche de collecte pour l'Annuaire statistique\n"]
    current = None
    for f in findings:
        if f.rubrique != current:
            current = f.rubrique
            lines.append(f"\n## {current}\n")
        nums = f" — **{', '.join(f.numbers)}**" if f.numbers else ""
        lines.append(f"- {f.sentence}{nums}  \n  _{f.citation}_")
    return "\n".join(lines)


def findings_to_csv(findings: List[Finding]) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Rubrique", "Constat", "Donnees_chiffrees", "Reference"])
    for f in findings:
        w.writerow([f.rubrique, f.sentence, " | ".join(f.numbers), f.citation])
    return buf.getvalue()
