"""
Génération du commentaire (cahier des charges, Étape 6) — client enfichable.

Deux régimes, sélectionnés au démarrage et inscrits dans les sorties :
  - RÉFÉRENCE — un LLM local (Ollama, point d'accès compatible OpenAI) rédige
    sous l'instruction en cinq blocs. Paramètres fixés (température 0,2, longueur
    maximale 700 jetons, graine), identiques pour toutes les configurations.
  - DÉGRADÉ — aucun modèle disponible : composition **extractive** déterministe
    à partir du bloc de données (valeurs de l'exercice) et de la forme des
    commentaires antérieurs. Aucune hallucination possible ; sert de repli et de
    borne de fidélité (configuration C4).

Dans les deux cas, la sortie est découpée en propositions (structured.py), puis
les garde-fous s'appliquent (guards/). Le générateur n'a aucune valeur en dur.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

from ..retrieval.context import Contexte
from ..guards.numeric import Proposition, extract_numbers
from .prompt import construire_prompt
from .structured import parser_propositions


@dataclass
class ResultatGeneration:
    propositions: List[Proposition] = field(default_factory=list)
    regime: str = "dégradé"            # "référence (llm:<modèle>)" | "dégradé (extractif)"
    texte_brut: str = ""


# --------------------------------------------------------------------------- #
#  Régime de référence : LLM local (Ollama)
# --------------------------------------------------------------------------- #
def _llm_config():
    base = os.environ.get("RAG_LLM_BASE_URL", "")
    model = os.environ.get("RAG_LLM_MODEL", "")
    return base, model


def _appel_llm(prompt: str, base: str, model: str, seed: int = 42,
               temperature: float = 0.2, max_tokens: int = 700) -> Optional[str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": seed,
    }
    # Clé d'API facultative : requise pour un fournisseur cloud compatible OpenAI
    # (OpenAI, Groq, Google Gemini…), inutile pour Ollama local. Le protocole est
    # le même dans les deux cas — seuls l'URL, le modèle et la clé changent.
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("RAG_LLM_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
#  Régime dégradé : composition extractive déterministe
# --------------------------------------------------------------------------- #
def _sans_nombres(texte: str) -> str:
    """Retire les valeurs chiffrées d'un commentaire antérieur pour n'en garder
    que la forme (règle : le patron vient du passé, jamais ses valeurs)."""
    t = re.sub(r"\d[\d   .,]*\d|\d", "…", texte)
    return re.sub(r"\s+", " ", t).strip()


def _composer_extractif(ctx: Contexte) -> str:
    lignes: List[str] = []
    for enonce in ctx.valeurs_n:
        # « Centre | stock = 3023 » -> proposition sourcée et grounded.
        m = re.match(r"(.*?)\s*=\s*(.+)$", enonce)
        if not m:
            continue
        libelle, valeur = m.group(1).strip(), m.group(2).strip()
        lignes.append(f"- Pour l'exercice {ctx.exercice}, {libelle} s'établit à {valeur}.")
    # Une phrase d'interprétation reprenant la FORME d'un commentaire antérieur,
    # débarrassée de ses valeurs (garde-fou : aucune valeur du passé reprise).
    if ctx.commentaires_anterieurs:
        forme = _sans_nombres(ctx.commentaires_anterieurs[0])
        if len(forme) > 15:
            lignes.append(f"- {forme}")
    return "\n".join(lignes)


# --------------------------------------------------------------------------- #
#  Point d'entrée
# --------------------------------------------------------------------------- #
def generer(ctx: Contexte, intitule: str, seed: int = 42) -> ResultatGeneration:
    """Génère les propositions du commentaire, LLM si disponible, sinon extractif."""
    base, model = _llm_config()
    if base and model:
        prompt = construire_prompt(ctx, intitule)
        brut = _appel_llm(prompt, base, model, seed=seed)
        if brut is not None:
            return ResultatGeneration(
                propositions=parser_propositions(brut, source_id=ctx.code_indicateur),
                regime=f"référence (llm:{model})", texte_brut=brut)
    # Repli déterministe.
    brut = _composer_extractif(ctx)
    return ResultatGeneration(
        propositions=parser_propositions(brut, source_id=ctx.code_indicateur),
        regime="dégradé (extractif)", texte_brut=brut)
