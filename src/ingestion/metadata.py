"""
Schéma de métadonnées documentaires et détection de l'exercice (Étape 1.5).

Règle du cahier des charges (§2, 3ᵉ particularité) : l'exercice de référence ne
se lit **jamais** sur le nom de fichier ni sur le titre courant — tous deux
erronés dans ce corpus (ex. l'Annuaire 2022 est le fichier `stat2023fr.pdf` ;
un Annuaire d'exercice 2023 porte un titre courant « 2022 »).

Approche retenue, documentée dans docs/JOURNAL.md : l'exercice est l'année
récente **dominante dans le corps du document**, corroborée par les mentions
explicites « (au titre de) l'exercice 20XX ». Cette règle a été vérifiée sur les
16 documents disponibles ; la page de titre seule échoue précisément sur les cas
pièges, car son en-tête reprend le titre courant erroné.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Optional

# Fenêtre d'années plausibles pour un exercice (bornes larges, sans valeur en dur
# ailleurs : ces bornes ne sont qu'un garde-fou de plausibilité).
_YEAR_RE = re.compile(r"\b(20(?:1[0-9]|2[0-9]))\b")
_EXERCICE_RE = re.compile(r"exercice\s+(20(?:1[0-9]|2[0-9]))", re.IGNORECASE)


@dataclass
class DocumentMeta:
    """Les huit métadonnées d'un document (Étape 1)."""
    doc_id: str                      # identifiant stable (nom canonique sans extension)
    type: str                        # annuaire | rapport_analyse | note_conjoncture | contexte
    exercice: Optional[int]          # année de l'exercice (données), cœur de l'appariement
    edition: Optional[int]           # année d'édition (publication), si détectable
    periode: str                     # ex. "T3 2024" pour une note de conjoncture, sinon ""
    titre: str                       # première ligne significative de la page de titre
    source_file: str                 # nom de fichier d'origine
    n_pages: int                     # nombre de pages
    structure: str = "MINPMEESA/DEPP"  # structure émettrice

    def to_dict(self) -> dict:
        return asdict(self)


def detect_exercice(full_text: str) -> Optional[int]:
    """Année de l'exercice = année récente dominante dans le corps, avec un bonus
    aux mentions explicites « exercice 20XX »."""
    years = _YEAR_RE.findall(full_text)
    if not years:
        return None
    freq = Counter(int(y) for y in years)
    # Renforce les années explicitement qualifiées d'« exercice ».
    for m in _EXERCICE_RE.findall(full_text):
        freq[int(m)] += 5
    # L'exercice est l'année la plus fréquente ; en cas d'égalité, la plus récente.
    best = max(freq.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0]


def detect_periode(full_text: str, source_file: str) -> str:
    """Repère un trimestre pour les notes de conjoncture (ex. « T3 2024 »)."""
    hay = f"{source_file}\n{full_text[:3000]}"
    m = re.search(r"(?<![A-Za-z])T\s?([1-4])[\s_/-]*(20\d{2})", hay, re.IGNORECASE)
    if not m:
        m = re.search(r"([1-4])(?:er|ème|e)?\s+trimestre\s+(20\d{2})", hay, re.IGNORECASE)
    if m:
        return f"T{m.group(1)} {m.group(2)}"
    return ""


def detect_type(full_text: str, source_file: str) -> str:
    """Type de document, déterminé par sa STRUCTURE (jamais par le seul mot-clé,
    car « conjoncture » et « perspective » apparaissent aussi dans les rapports).

    - un Rapport d'analyse commente de nombreux « Graphique N » ;
    - un Annuaire est une collection de « Tableau N » ;
    - une note de conjoncture s'intitule « note de conjoncture » et porte un
      trimestre, sans catalogue de graphiques ou de tableaux ;
    - les bulletins et notes de perspective sont des documents de contexte.
    """
    fn = source_file.lower()
    head = full_text[:1500].lower()
    n_graph = len(set(re.findall(r"graphique\s+(\d+)", full_text, re.IGNORECASE)))
    n_tab = len(set(re.findall(r"tableau\s+(\d+)", full_text, re.IGNORECASE)))
    has_trimestre = bool(detect_periode(full_text, source_file))

    # 1) Note de conjoncture : titre explicite, ou trimestre sans gros catalogue.
    if ("note de conjoncture" in head or fn.startswith("note_conjoncture")
            or (has_trimestre and n_graph < 5 and n_tab < 10)):
        return "note_conjoncture"
    # 2) Contexte : bulletins et notes de perspective. Une note de perspective
    #    comporte aussi des graphiques : on la reconnaît à son TITRE, jamais au
    #    simple mot « perspective » (présent dans les rapports et annuaires).
    if ("bulletin d" in head or "note de perspective" in head
            or fn.startswith("contexte_")):
        return "contexte"
    # 3) Annuaire : titre « annuaire statistique » et catalogue de tableaux.
    if ("annuaire statistique" in head and n_tab >= 10) or (
            fn.startswith("annuaire") and n_tab >= 10):
        return "annuaire"
    # 4) Rapport d'analyse : commentaire riche en graphiques.
    if n_graph >= 5 and n_graph >= n_tab:
        return "rapport_analyse"
    # 5) Repli : le signal structurel le plus fort.
    if n_tab >= 10:
        return "annuaire"
    if n_graph > n_tab:
        return "rapport_analyse"
    return "contexte"


def build_meta(doc_id: str, source_file: str, full_text: str, n_pages: int) -> DocumentMeta:
    dtype = detect_type(full_text, source_file)
    exercice = detect_exercice(full_text)
    periode = detect_periode(full_text, source_file) if dtype == "note_conjoncture" else ""
    # Édition : une année de publication postérieure à l'exercice, si mentionnée
    # (ex. « Mai 2025 » pour un rapport d'exercice 2024). Détection best-effort.
    edition = None
    m = re.search(r"(janvier|février|mars|avril|mai|juin|juillet|ao[uû]t|"
                  r"septembre|octobre|novembre|décembre)\s+(20\d{2})",
                  full_text[:2000], re.IGNORECASE)
    if m:
        edition = int(m.group(2))
    titre = ""
    for line in full_text.splitlines():
        line = line.strip()
        if len(line) > 8:
            titre = line
            break
    return DocumentMeta(doc_id=doc_id, type=dtype, exercice=exercice, edition=edition,
                        periode=periode, titre=titre[:120], source_file=source_file,
                        n_pages=n_pages)
