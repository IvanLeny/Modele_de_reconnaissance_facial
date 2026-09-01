"""
Segmentation en passages (chapitre 3.2).

Stratégie : fenêtre glissante par nombre de mots, avec recouvrement, guidée par
la structure. Les frontières de section et de page sont respectées autant que
possible pour ne pas séparer une donnée de son contexte immédiat. Les passages
denses en chiffres (tableaux) sont conservés d'un seul tenant sous un plafond de
taille, afin de ne jamais couper une ligne de chiffres de son en-tête.

Chaque passage reçoit un identifiant stable et hérite des métadonnées du
document (statut de diffusion, type, année, trimestre) : c'est ce qui permet
ensuite le filtrage par mode et la traçabilité de chaque citation.
"""
from __future__ import annotations

import re
from typing import List

from ..config import IngestionConfig
from ..schema import Chunk, DocumentMeta
from ..index.text_utils import tokenize_fr, FUNCTION_WORDS_FR
from .extract import PageElement

_DIGIT_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"\S+")
_DECIMAL_RE = re.compile(r"\d[.,]\d")   # 69,80  5,7  3.2 — pourcentages et décimales
_INT3_RE = re.compile(r"^\d{3,}$")      # entier à 3 chiffres ou plus


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _is_meaningful_number(tok: str) -> bool:
    """Une vraie statistique : décimale/pourcentage, ou grand entier — mais pas
    un simple ordinal (1, 2, 5) ni un millésime isolé (2023)."""
    if _DECIMAL_RE.search(tok):
        return True
    if _INT3_RE.match(tok):
        if len(tok) == 4 and 1900 <= int(tok) <= 2099:   # millésime isolé
            return False
        return True
    return False


def compute_informativeness(text: str) -> float:
    """
    Indice d'informativité dans [0,1] (chap. 3.2).

    Un passage est jugé informatif s'il est SOIT une prose rédigée (forte densité
    de mots-outils), SOIT un tableau porteur de chiffres RÉELS (nombres à trois
    chiffres ou plus). Un passage « creux » — sommaire, formulaire d'annexe, liste
    d'intitulés aux champs vides — présente une densité de mots-outils moyenne
    (quelques « de », « et ») mais SANS verbe ni vraie statistique : il tombe dans
    la zone morte des deux critères et reçoit un indice bas, ce qui le fait reculer
    au classement sans jamais l'exclure.

    Calibrage (mesuré sur le corpus) : prose rédigée -> mots-outils >= 0,42 ;
    tableau de données -> grands nombres >= 0,20 ; formulaires d'annexe -> les
    deux nettement en dessous.
    """
    tokens = tokenize_fr(text, keep_stopwords=True)
    if not tokens:
        return 0.15
    n = len(tokens)
    func_ratio = sum(1 for t in tokens if t in FUNCTION_WORDS_FR) / n
    num_ratio = sum(1 for t in tokens if _is_meaningful_number(t)) / n
    prose = _clamp01((func_ratio - 0.20) / (0.42 - 0.20))
    data = _clamp01((num_ratio - 0.05) / (0.18 - 0.05))
    return max(0.15, prose, data)


def _count_numbers(text: str) -> bool:
    return len(_DIGIT_RE.findall(text)) >= 2


# Motif de légende de sommaire : « Tableau 4 : … » / « Graphique 2 : … »
_CAPTION_RE = re.compile(r"(Tableau|Graphique|Figure)\s+\d+\s*:", re.IGNORECASE)


def _is_toc(text: str) -> bool:
    """Détecte un passage de sommaire / liste des tableaux (navigationnel, non informatif)."""
    captions = _CAPTION_RE.findall(text)
    if len(captions) >= 3:
        # Beaucoup de légendes et peu de phrases : c'est une table des matières.
        return True
    return False


# Intitulés de champs typiques des formulaires d'annexe (canevas de collecte).
_FORM_LABEL_RE = re.compile(
    r"\b(nombre d|effectif|montant total|taux de|valeur des|total\b|autres à préciser)",
    re.IGNORECASE)


def _is_empty_form(text: str) -> bool:
    """
    Détecte un formulaire d'annexe « vide » : un canevas de collecte fait
    d'intitulés de champs (« Nombre de… », « Total », « Effectif ») mais sans
    aucune donnée chiffrée renseignée. Ces pages, purement structurelles, n'ont
    aucune valeur informative et polluent la recherche par simple correspondance
    de mots-clés ; elles sont donc écartées de l'index.

    Critère (calibré sur le corpus) : au moins 6 intitulés de champs ET au plus
    2 statistiques réelles — ce qui distingue nettement un canevas vide d'un vrai
    tableau de données (des dizaines de nombres).
    """
    labels = len(_FORM_LABEL_RE.findall(text))
    if labels < 6:
        return False
    meaningful = sum(1 for t in tokenize_fr(text, keep_stopwords=True)
                     if _is_meaningful_number(t))
    return meaningful <= 2


def _split_paragraphs(text: str) -> List[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(
    elements: List[PageElement],
    meta: DocumentMeta,
    cfg: IngestionConfig,
) -> List[Chunk]:
    """Segmente les éléments d'un document en passages indexables."""
    chunks: List[Chunk] = []
    counter = 0

    # On agrège paragraphe par paragraphe en respectant la taille cible.
    buffer_words: List[str] = []
    buffer_pages: List[int] = []
    buffer_section = ""
    buffer_is_table = False

    def flush():
        nonlocal counter, buffer_words, buffer_pages, buffer_section, buffer_is_table
        if not buffer_words:
            return
        text = " ".join(buffer_words).strip()
        wc = len(buffer_words)
        if wc >= cfg.min_chunk_words and not _is_toc(text) and not _is_empty_form(text):
            page_start = min(buffer_pages)
            page_end = max(buffer_pages)
            chunk_id = f"{meta.doc_id}::c{counter:04d}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=meta.doc_id,
                text=text,
                page_start=page_start,
                page_end=page_end,
                section=buffer_section,
                is_table=buffer_is_table or _count_numbers(text) and (
                    len(_DIGIT_RE.findall(text)) / max(1, len(text)) > 0.06),
                contains_numbers=_count_numbers(text),
                doc_title=meta.title,
                doc_type=meta.doc_type,
                diffusion_status=meta.diffusion_status,
                year=meta.year,
                quarter=meta.quarter,
                word_count=wc,
                informativeness=compute_informativeness(text),
            ))
            counter += 1
        buffer_words = []
        buffer_pages = []
        buffer_is_table = False

    for el in elements:
        for para in _split_paragraphs(el.text):
            words = _WORD_RE.findall(para)
            if not words:
                continue
            para_is_table = el.is_table and (
                len(_DIGIT_RE.findall(para)) / max(1, len(para)) > 0.06)

            # Un tableau compact est émis d'un seul tenant.
            if para_is_table and len(words) <= cfg.table_max_words:
                flush()
                buffer_words = words
                buffer_pages = [el.page]
                buffer_section = el.section
                buffer_is_table = True
                flush()
                continue

            # Sinon, fenêtre glissante par mots.
            if not buffer_words:
                buffer_section = el.section
            if el.page not in buffer_pages:
                buffer_pages.append(el.page)
            buffer_words.extend(words)

            while len(buffer_words) >= cfg.chunk_size_words:
                head = buffer_words[:cfg.chunk_size_words]
                counter_before = counter
                # émettre 'head'
                saved_words = buffer_words
                buffer_words = head
                flush()
                # recouvrement : conserver la queue
                overlap = saved_words[cfg.chunk_size_words - cfg.chunk_overlap_words:]
                buffer_words = overlap
                buffer_pages = [el.page]
                buffer_section = el.section
        # frontière de section forte : on vide le tampon aux changements majeurs
        # (laissé au recouvrement naturel ; flush explicite en fin de doc)
    flush()
    return chunks
