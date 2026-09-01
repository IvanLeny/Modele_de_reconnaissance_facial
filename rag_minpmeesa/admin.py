"""
Administration du corpus (chapitre 3.7, mise à jour de la documentation).

Fonctions d'ajout, de mise à jour et de suppression de documents dans le corpus,
avec tenue du registre de métadonnées, puis reconstruction de l'index. C'est ce
qui permet à l'utilisateur d'enrichir la base documentaire directement depuis
l'interface, sans toucher au code — pour alimenter le système au fil des
nouvelles éditions (nouvelles notes de conjoncture, rapports d'activité, etc.).
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import DiffusionStatus, get_settings


REGISTRY_HEADER = (
    "Registre du corpus : métadonnées de niveau document (chap. 3.2). "
    "Le champ 'diffusion_status' (interne|publie) porte le cloisonnement des "
    "deux modes (plan A.2)."
)


@dataclass
class DocRow:
    doc_id: str
    title: str
    source_file: str
    doc_type: str
    diffusion_status: str
    year: Optional[int]
    quarter: Optional[str]
    exists: bool


# --------------------------------------------------------------------------- #
#  Lecture / écriture du registre
# --------------------------------------------------------------------------- #
def _read_registry() -> dict:
    reg = get_settings().paths.registry_file
    if reg.exists():
        return json.loads(reg.read_text(encoding="utf-8"))
    return {"_comment": REGISTRY_HEADER, "documents": []}


def _write_registry(data: dict) -> None:
    reg = get_settings().paths.registry_file
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Opérations
# --------------------------------------------------------------------------- #
def list_documents() -> List[DocRow]:
    """Liste les documents déclarés au registre, avec présence du fichier."""
    settings = get_settings()
    data = _read_registry()
    rows: List[DocRow] = []
    for e in data.get("documents", []):
        path = settings.paths.corpus_dir / e["source_file"]
        rows.append(DocRow(
            doc_id=e["doc_id"], title=e["title"], source_file=e["source_file"],
            doc_type=e["doc_type"], diffusion_status=e.get("diffusion_status", "publie"),
            year=e.get("year"), quarter=e.get("quarter"), exists=path.exists(),
        ))
    return rows


def _slugify(name: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in name]
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "document"


def add_or_update_document(
    title: str,
    doc_type: str,
    diffusion_status: str,
    year: Optional[int] = None,
    quarter: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    original_filename: Optional[str] = None,
    doc_id: Optional[str] = None,
) -> str:
    """
    Ajoute ou met à jour un document. Si `file_bytes` est fourni, le PDF est
    enregistré dans le corpus. Renvoie le doc_id.
    """
    settings = get_settings()
    DiffusionStatus(diffusion_status)  # valide la valeur

    if doc_id is None:
        base = _slugify(Path(original_filename).stem if original_filename else title)
        doc_id = base
    source_file = f"{doc_id}.pdf"

    if file_bytes is not None:
        settings.paths.corpus_dir.mkdir(parents=True, exist_ok=True)
        (settings.paths.corpus_dir / source_file).write_bytes(file_bytes)

    data = _read_registry()
    docs = data.setdefault("documents", [])
    entry = {
        "doc_id": doc_id, "source_file": source_file, "title": title,
        "doc_type": doc_type, "diffusion_status": diffusion_status,
        "year": year, "quarter": quarter,
    }
    for i, e in enumerate(docs):
        if e["doc_id"] == doc_id:
            docs[i] = entry
            break
    else:
        docs.append(entry)
    _write_registry(data)
    return doc_id


def delete_document(doc_id: str, remove_file: bool = True) -> bool:
    """Retire un document du registre (et son fichier si demandé)."""
    settings = get_settings()
    data = _read_registry()
    docs = data.get("documents", [])
    kept, removed = [], None
    for e in docs:
        if e["doc_id"] == doc_id:
            removed = e
        else:
            kept.append(e)
    if removed is None:
        return False
    data["documents"] = kept
    _write_registry(data)
    if remove_file:
        f = settings.paths.corpus_dir / removed["source_file"]
        if f.exists():
            f.unlink()
    return True


def rebuild_index(verbose: bool = False) -> dict:
    """Reconstruit l'index à partir du corpus courant. Renvoie les métadonnées."""
    from .engine import RAGEngine
    eng = RAGEngine(verbose=verbose).build_index()
    return eng.store.meta


_ASSETS = Path(__file__).resolve().parent / "app" / "assets"

# Ressources visuelles reconnues par l'interface (chap. 3.7).
ASSET_NAMES = {
    "logo": "Logo de la structure (en-tête)",
    "banniere": "Bannière / photo institutionnelle (haut de page)",
    "couverture": "Couverture de l'Annuaire (barre latérale)",
}


def save_asset(name: str, file_bytes: bytes, extension: str = "png") -> Path:
    """Enregistre une ressource visuelle nommée (logo, banniere, couverture)."""
    if name not in ASSET_NAMES:
        raise ValueError(f"Ressource inconnue : {name}")
    _ASSETS.mkdir(parents=True, exist_ok=True)
    for old in _ASSETS.glob(f"{name}.*"):
        old.unlink()
    target = _ASSETS / f"{name}.{extension.lstrip('.').lower()}"
    target.write_bytes(file_bytes)
    return target


def find_asset(name: str) -> Optional[Path]:
    """Retrouve une ressource visuelle nommée si elle a été déposée."""
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        p = _ASSETS / f"{name}.{ext}"
        if p.exists():
            return p
    return None


# Compatibilité (en-tête) : le logo reste la ressource « logo ».
def save_logo(file_bytes: bytes, extension: str = "png") -> Path:
    return save_asset("logo", file_bytes, extension)


def find_logo() -> Optional[Path]:
    return find_asset("logo")
