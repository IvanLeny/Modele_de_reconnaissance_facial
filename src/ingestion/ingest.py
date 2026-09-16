"""
Ingestion du corpus dans le dépôt (cahier des charges, Étapes 1-2-4a réunies).

Peuple le `Store` (SQLite ici, PostgreSQL sur la machine cible) :
  - valeurs linéarisées des Annuaires (tableaux) ;
  - commentaires des Rapports d'analyse, segmentés par graphique et rattachés à
    un code indicateur via la table d'appariement ;
  - lignes d'appariement.

Fournit aussi, pour l'évaluation, le **commentaire publié de référence** de
chaque (code indicateur, exercice) = le segment du rapport associé au graphique.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .extract import extract_document
from .metadata import build_meta
from .tables import extract_tables
from ..retrieval.store import Store, PassageRow, ValeurRow
from ..pairing.build import build_pairs, extract_graphiques, code_indicateur


COUPLES = {
    2021: ("rapport_analyse_2021", "annuaire_2021"),
    2022: ("rapport_analyse_2022", "annuaire_2022"),
    2023: ("rapport_analyse_2023", "annuaire_2023"),
    2024: ("rapport_analyse_2024", "annuaire_2024"),
}


def segmenter_commentaires(rapport_path: str) -> Dict[int, str]:
    """Commentaire associé à chaque graphique : la prose du corps, PAS l'entrée du
    sommaire (« Liste des graphiques »). Les entrées de sommaire se reconnaissent
    à leurs points de conduite suivis d'un numéro de page ; on les écarte."""
    ft = extract_document(rapport_path).full_text()
    marqueurs = [(int(m.group(1)), m.start(), m.end())
                 for m in re.finditer(r"Graphique\s+(\d+)\s*[:.\-–]", ft, re.I)]
    marqueurs.sort(key=lambda x: x[1])
    # Filtre les entrées de sommaire : légende suivie de « ....… 8 » (points de
    # conduite + numéro de page) dans les ~200 caractères qui suivent.
    corps = [(n, s, e) for (n, s, e) in marqueurs
             if not re.search(r"\.{4,}\s*\d+", ft[e:e + 200])]
    out: Dict[int, str] = {}
    for i, (n, s, e) in enumerate(corps):
        fin = corps[i + 1][1] if i + 1 < len(corps) else min(len(ft), s + 1400)
        seg = re.sub(r"\s+", " ", ft[s:fin]).strip()
        if len(seg) > 60 and n not in out:
            out[n] = seg[:1200]
    return out


@dataclass
class Referentiel:
    """Références d'évaluation : commentaire publié par (exercice, code)."""
    reference: Dict[Tuple[int, str], str] = field(default_factory=dict)
    intitule: Dict[Tuple[int, str], str] = field(default_factory=dict)


def populate(store, corpus_dir: str = "data/corpus", verbose: bool = False) -> Referentiel:
    """Peuple un dépôt QUELCONQUE (SQLite ou PostgreSQL) depuis le corpus et
    renvoie les références d'évaluation. Le dépôt doit exposer l'interface
    add_document / add_valeur / add_passage / add_appariement / commit."""
    corpus = Path(corpus_dir)
    ref = Referentiel()

    for exercice, (rap, ann) in COUPLES.items():
        rap_path, ann_path = corpus / f"{rap}.pdf", corpus / f"{ann}.pdf"
        if not rap_path.exists() or not ann_path.exists():
            continue
        # Documents.
        store.add_document(ann, "annuaire", exercice, source_file=ann_path.name)
        store.add_document(rap, "rapport_analyse", exercice, source_file=rap_path.name)

        # Valeurs des tableaux de l'Annuaire.
        for t in extract_tables(str(ann_path)):
            for c in t.cellules:
                store.add_valeur(ValeurRow(exercice=exercice, ligne=c.ligne,
                                           colonne=c.colonne, valeur=c.valeur,
                                           doc_id=ann, tableau_n=None, page=t.page))

        # Commentaires du Rapport, par graphique -> code indicateur.
        graphs = {g.numero: g.intitule for g in extract_graphiques(str(rap_path))}
        segments = segmenter_commentaires(str(rap_path))
        for n, intitule in graphs.items():
            code = code_indicateur(intitule)
            store.add_appariement(code, exercice, n, None, intitule)
            texte = segments.get(n, "")
            if texte:
                store.add_passage(PassageRow(exercice=exercice, code_indicateur=code,
                                             texte=texte, doc_id=rap, section=f"Graphique {n}"))
                ref.reference[(exercice, code)] = texte
                ref.intitule[(exercice, code)] = intitule
        if verbose:
            print(f"  exercice {exercice}: {len(graphs)} graphiques, "
                  f"{len(segments)} commentaires segmentés")
    store.commit()
    return ref


def build_store(corpus_dir: str = "data/corpus", verbose: bool = False) -> Tuple[Store, Referentiel]:
    """Construit un dépôt SQLite en mémoire peuplé (développement/évaluation)."""
    store = Store(":memory:")
    ref = populate(store, corpus_dir, verbose)
    return store, ref
