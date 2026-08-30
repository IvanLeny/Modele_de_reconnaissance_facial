"""
Chargement du registre du corpus (métadonnées de niveau document).

Le registre (data/corpus/registry.json) donne pour chaque fichier son titre,
son type, son statut de diffusion et ses attributs temporels. Si un fichier
présent dans le corpus n'y figure pas, ses métadonnées sont inférées du nom de
fichier — de sorte que le système reste opérationnel même sans registre complet.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

from ..config import DiffusionStatus, get_settings
from ..schema import DocumentMeta


def _infer_from_filename(path: Path) -> DocumentMeta:
    """Métadonnées de repli déduites du nom de fichier."""
    stem = path.stem
    name = stem.lower()
    year = None
    m = re.search(r"(20\d{2})", name)
    if m:
        year = int(m.group(1))
    quarter = None
    mq = re.search(r"t([1-4])", name)
    if mq:
        quarter = "T" + mq.group(1)
    if "annuaire" in name:
        doc_type = "annuaire_statistique"
    elif "conjoncture" in name or quarter:
        doc_type = "note_conjoncture"
    else:
        doc_type = "document"
    return DocumentMeta(
        doc_id=stem,
        title=stem.replace("_", " "),
        source_file=path.name,
        doc_type=doc_type,
        diffusion_status=DiffusionStatus.PUBLIE,
        year=year,
        quarter=quarter,
    )


def load_registry() -> Dict[str, DocumentMeta]:
    """Renvoie {doc_id: DocumentMeta} pour tous les PDF du dossier corpus."""
    settings = get_settings()
    corpus_dir = settings.paths.corpus_dir
    registry_file = settings.paths.registry_file

    declared: Dict[str, dict] = {}
    if registry_file.exists():
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        for entry in data.get("documents", []):
            declared[entry["source_file"]] = entry

    metas: Dict[str, DocumentMeta] = {}
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        entry = declared.get(pdf.name)
        if entry:
            metas[entry["doc_id"]] = DocumentMeta(
                doc_id=entry["doc_id"],
                title=entry["title"],
                source_file=entry["source_file"],
                doc_type=entry["doc_type"],
                diffusion_status=DiffusionStatus(entry.get("diffusion_status", "publie")),
                year=entry.get("year"),
                quarter=entry.get("quarter"),
            )
        else:
            meta = _infer_from_filename(pdf)
            metas[meta.doc_id] = meta
    return metas
