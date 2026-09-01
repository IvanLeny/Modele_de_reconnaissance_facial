"""
Restitution ancrée dans les sources (chapitres 3.5 et 3.6).

Deux formes de restitution, gouvernées par la configuration :

  - EXTRACTIVE (défaut, souverain) : la synthèse est composée de phrases reprises
    VERBATIM des passages sources, chacune suivie de sa référence. Par
    construction, aucune donnée chiffrée n'est reformulée ni recalculée : le
    risque d'hallucination numérique est nul. C'est la restitution la plus
    défendable pour un corpus statistique.

  - LLM (optionnel) : un modèle de langage LOCAL rédige une synthèse à partir du
    seul contexte fourni, sous une consigne stricte (règle de citation littérale).
    Les garde-fous numérique et de fidélité s'appliquent ensuite à sa sortie ;
    toute donnée chiffrée non retrouvée dans les sources est signalée. Cette voie
    n'est activée que si un point d'accès LLM local est configuré.

Dans les deux cas, l'objet `Answer` porte la synthèse, la liste des passages
sourcés, l'audit numérique et le rapport de fidélité — de quoi tracer et
justifier chaque élément restitué.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..config import Mode, Settings, get_settings
from ..schema import RetrievalResult
from ..index.text_utils import tokenize_fr
from .context import ContextBlock, build_context, render_context
from .numeric import audit_numbers, NumericAudit, extract_numbers, number_supported
from .guardrails import faithfulness_report, FaithfulnessReport, split_sentences


# Consigne de rédaction contrôlée (utilisée en mode LLM) — matérialise la règle
# de restitution du plan A.2. Reproduite ici pour documenter le dispositif.
LLM_SYSTEM_PROMPT = (
    "Tu es un assistant documentaire du MINPMEESA. Réponds UNIQUEMENT à partir "
    "des passages numérotés fournis. Règles impératives : "
    "(1) n'invente aucune information ; si le contexte ne permet pas de répondre, "
    "dis-le explicitement. "
    "(2) Toute donnée chiffrée doit être reprise LITTÉRALEMENT d'un passage "
    "(aucun recalcul, aucun arrondi, aucune reformulation du nombre). "
    "(3) Fais suivre chaque affirmation de l'identifiant de sa source, par ex. [S1]. "
    "(4) Rédige de façon concise et neutre, en français."
)


@dataclass
class SourcedSentence:
    text: str
    sid: str
    citation: str


@dataclass
class Answer:
    query: str
    mode: str
    summary: str
    sentences: List[SourcedSentence] = field(default_factory=list)
    context: List[ContextBlock] = field(default_factory=list)
    numeric_audit: Optional[NumericAudit] = None
    faithfulness: Optional[FaithfulnessReport] = None
    synthesis_method: str = "extractive"
    refused: bool = False
    message: str = ""

    @property
    def sources(self) -> List[str]:
        seen, out = set(), []
        for b in self.context:
            key = b.result.chunk.doc_id + str(b.result.chunk.page_start)
            if key not in seen:
                seen.add(key)
                out.append(b.citation)
        return out

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "mode": self.mode,
            "synthesis_method": self.synthesis_method,
            "refused": self.refused,
            "message": self.message,
            "summary": self.summary,
            "sentences": [s.__dict__ for s in self.sentences],
            "sources": self.sources,
            "passages": [
                {"sid": b.sid, "citation": b.citation,
                 "doc_id": b.result.chunk.doc_id,
                 "pages": [b.result.chunk.page_start, b.result.chunk.page_end],
                 "text": b.text}
                for b in self.context
            ],
            "numeric_audit": self.numeric_audit.to_dict() if self.numeric_audit else None,
            "faithfulness": self.faithfulness.to_dict() if self.faithfulness else None,
        }


class Answerer:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    # ------------------------------------------------------------------ #
    def answer(self, query: str, results: List[RetrievalResult],
               mode: Mode = Mode.PRODUCTION) -> Answer:
        gcfg = self.settings.generation
        blocks = build_context(results, max_chars=gcfg.max_context_chars)

        if not blocks:
            return Answer(
                query=query, mode=Mode(mode).value, summary="",
                refused=True,
                message="Aucun passage pertinent n'a été trouvé dans le corpus "
                        "autorisé pour ce mode. Aucune réponse n'est produite.",
                synthesis_method=gcfg.synthesis,
            )

        if gcfg.synthesis == "llm":
            summary, method = self._synthesize_llm(query, blocks)
            if summary is None:  # repli si LLM indisponible
                summary = self._synthesize_extractive(query, blocks)
                method = "extractive (repli : LLM indisponible)"
        else:
            summary = self._synthesize_extractive(query, blocks)
            method = "extractive"

        context_texts = [b.text for b in blocks]

        # Garde-fou numérique : retirer les phrases portant un chiffre non sourcé.
        if gcfg.enforce_literal_numbers:
            summary = self._strip_unsupported_numbers(summary, context_texts)

        audit = audit_numbers(summary, context_texts)
        faith = faithfulness_report(summary, context_texts,
                                    threshold=gcfg.support_overlap_threshold)

        sentences = self._attach_sources(summary, blocks)
        return Answer(
            query=query, mode=Mode(mode).value, summary=summary,
            sentences=sentences, context=blocks,
            numeric_audit=audit, faithfulness=faith,
            synthesis_method=method,
        )

    # ------------------------------------------------------------------ #
    def _synthesize_extractive(self, query: str, blocks: List[ContextBlock]) -> str:
        """Sélectionne les phrases sources les plus pertinentes pour la requête."""
        gcfg = self.settings.generation
        q_tokens = set(tokenize_fr(query))
        candidates: List[Tuple[float, int, str]] = []
        for bi, b in enumerate(blocks):
            for sent in split_sentences(b.text):
                raw_toks = tokenize_fr(sent)
                toks = set(raw_toks)
                if not toks:
                    continue
                overlap = len(q_tokens & toks) / (len(q_tokens) or 1)
                if overlap <= 0:
                    continue
                # Qualité de prose : privilégie les phrases rédigées et pénalise
                # les amas d'étiquettes de graphiques (suites de nombres isolés,
                # fréquents dans la mise en page multi-colonnes des PDF).
                alpha_words = [t for t in raw_toks if t.isalpha() and len(t) > 2]
                digit_tokens = [t for t in raw_toks if any(ch.isdigit() for ch in t)]
                if len(alpha_words) < 4:
                    continue
                # Rejet des « listes d'intitulés » (formulaires d'annexe, sommaires) :
                # une vraie phrase porte des mots-outils OU une statistique réelle.
                from ..index.text_utils import FUNCTION_WORDS_FR
                func_ratio = sum(1 for t in raw_toks if t in FUNCTION_WORDS_FR) / len(raw_toks)
                has_real_number = any(len(re.sub(r"\D", "", t)) >= 3 for t in digit_tokens)
                if func_ratio < 0.18 and not has_real_number:
                    continue
                digit_ratio = len(digit_tokens) / max(1, len(raw_toks))
                prose_bonus = 1.0 if digit_ratio < 0.35 else 0.5
                length_penalty = 1.0 if 5 <= len(raw_toks) <= 70 else 0.6
                # Dans un corpus statistique, une phrase porteuse d'une donnée
                # chiffrée réelle répond souvent directement à la question.
                number_bonus = 0.25 if has_real_number else 0.0
                score = overlap * length_penalty * prose_bonus + number_bonus - 0.001 * bi
                candidates.append((score, bi, sent.strip()))
        candidates.sort(key=lambda x: x[0], reverse=True)

        chosen: List[str] = []
        seen = set()
        for score, bi, sent in candidates:
            key = sent[:60].lower()
            if key in seen:
                continue
            seen.add(key)
            chosen.append(sent)
            if len(chosen) >= gcfg.max_summary_sentences:
                break
        return " ".join(chosen)

    def _strip_unsupported_numbers(self, summary: str, context_texts: List[str]) -> str:
        """Supprime les phrases contenant une donnée chiffrée non sourcée."""
        kept = []
        for sent in split_sentences(summary):
            ok = True
            for mention in extract_numbers(sent):
                if not number_supported(mention, context_texts):
                    ok = False
                    break
            if ok:
                kept.append(sent)
        return " ".join(kept)

    def _attach_sources(self, summary: str,
                        blocks: List[ContextBlock]) -> List[SourcedSentence]:
        """Rattache chaque phrase de la synthèse au passage dont elle provient."""
        out: List[SourcedSentence] = []
        for sent in split_sentences(summary):
            best_sid, best_cit, best = blocks[0].sid, blocks[0].citation, -1.0
            s_tokens = set(tokenize_fr(sent))
            for b in blocks:
                ov = len(s_tokens & set(tokenize_fr(b.text))) / (len(s_tokens) or 1)
                if ov > best:
                    best, best_sid, best_cit = ov, b.sid, b.citation
            out.append(SourcedSentence(text=sent, sid=best_sid, citation=best_cit))
        return out

    # ------------------------------------------------------------------ #
    def _synthesize_llm(self, query: str,
                        blocks: List[ContextBlock]) -> Tuple[Optional[str], str]:
        """
        Rédaction par un LLM local (optionnel). Utilise un point d'accès compatible
        OpenAI défini par les variables d'environnement RAG_LLM_BASE_URL /
        RAG_LLM_MODEL (par ex. un serveur Ollama local). Renvoie (None, "") si
        indisponible, pour bascule sur l'extractif.
        """
        base = os.environ.get("RAG_LLM_BASE_URL")
        model = os.environ.get("RAG_LLM_MODEL")
        if not base or not model:
            return None, ""
        try:
            import json
            import urllib.request
            context = render_context(blocks)
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user",
                     "content": f"Contexte :\n{context}\n\nQuestion : {query}"},
                ],
                "temperature": 0.0,
            }
            req = urllib.request.Request(
                base.rstrip("/") + "/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip(), "llm"
        except Exception:
            return None, ""
