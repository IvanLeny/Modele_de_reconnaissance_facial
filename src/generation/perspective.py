"""
Note d'analyse de perspective (aide à la décision) — extension demandée par
l'encadrement.

Au-delà du commentaire d'UN indicateur, le système produit une **note de
perspective** synthétique à partir de TOUT le corpus (annuaires, rapports, notes
de conjoncture, documents de contexte), destinée aux décideurs.

Mêmes garanties que la génération de commentaire (garde-fous indépendants du
modèle) :
  - tout nombre cité est repris LITTÉRALEMENT des valeurs de la base
    (bloc de données = chiffres-clés extraits) ; une valeur non appariée est
    retirée et signalée ;
  - la partie prospective est de la prose interprétative, sourcée aux documents
    qu'elle synthétise, jamais des chiffres inventés ;
  - le système s'abstient si les chiffres-clés font défaut.

Régime RÉFÉRENCE (Ollama) : rédaction fluide et structurée. Régime DÉGRADÉ :
squelette structuré et ancré (chiffres-clés + tendances/patrons dont les valeurs
sont neutralisées), suffisant pour démontrer la structure et les garanties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..retrieval.store import Store
from ..guards.numeric import controler_propositions, Proposition, AuditNumerique
from ..generation.generate import _llm_config, _appel_llm, _sans_nombres
from ..generation.structured import parser_propositions


THEMES = [
    "Répartition du stock de PME par région",
    "Stock de PME par secteur d'activité",
    "PME créées dans les CFCE",
    "Trésorerie et financement des PME",
    "Emplois créés par les PME",
]


@dataclass
class ContextePerspective:
    exercice: int
    figures: List[str] = field(default_factory=list)          # « ligne | colonne = valeur »
    tendances: List[str] = field(default_factory=list)         # passages de conjoncture
    patrons: List[str] = field(default_factory=list)           # notes de perspective (forme)
    sources: List[str] = field(default_factory=list)

    def bloc_donnees(self) -> str:
        return "\n".join(self.figures)


@dataclass
class NotePerspective:
    exercice: int
    texte: str = ""
    propositions: List[Proposition] = field(default_factory=list)
    audit: AuditNumerique = None
    regime: str = "dégradé (extractif)"
    sources: List[str] = field(default_factory=list)


_BOILERPLATE = ("liste des graphiques", "liste des tableaux", "sommaire",
                "ministere des", "ministry of", "republique du cameroun",
                "table des matieres")


def _substantiel(texte: str) -> bool:
    """Écarte les passages non informatifs (en-têtes, sommaires, listes) :
    trop de majuscules ou contenant des marqueurs de boilerplate."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    if any(b in t for b in _BOILERPLATE):
        return False
    import re
    if re.search(r"\.{6,}", texte):               # points de conduite (sommaire)
        return False
    lettres = [c for c in texte if c.isalpha()]
    if lettres and sum(1 for c in lettres if c.isupper()) / len(lettres) > 0.4:
        return False
    return len(texte.split()) >= 20


def assembler_contexte(store: Store, exercice: int) -> ContextePerspective:
    ctx = ContextePerspective(exercice=exercice)
    srcs = set()
    vus = set()
    for th in THEMES:
        for r in store.valeurs_indicateur(exercice, th, limit=8):
            col = f" | {r['colonne']}" if r["colonne"] else ""
            enonce = f"{r['ligne']}{col} = {r['valeur']}"
            if enonce not in vus:                 # dédoublonnage des chiffres-clés
                vus.add(enonce)
                ctx.figures.append(enonce)
                if r["doc_id"]:
                    srcs.add(r["doc_id"])
    for p in store.passages_par_type("note_conjoncture", limit=30, exercice_max=exercice):
        if _substantiel(p["texte"]) and len(ctx.tendances) < 5:
            ctx.tendances.append(p["texte"])
            srcs.add(p["doc_id"])
    for p in store.passages_par_type("contexte", limit=30):
        if _substantiel(p["texte"]) and len(ctx.patrons) < 3:
            ctx.patrons.append(p["texte"])
            srcs.add(p["doc_id"])
    ctx.sources = sorted(srcs)
    return ctx


# --------------------------------------------------------------------------- #
#  Instruction (régime de référence)
# --------------------------------------------------------------------------- #
def construire_prompt(ctx: ContextePerspective) -> str:
    figures = "\n".join(ctx.figures) or "(aucun chiffre-clé)"
    tendances = "\n".join(f"- {t}" for t in ctx.tendances) or "(aucune)"
    patrons = "\n".join(f"- {p}" for p in ctx.patrons) or "(aucun)"
    regles = (
        "RÈGLES (impératives) : n'emploie QUE les valeurs du bloc CHIFFRES-CLÉS ; "
        "ne procède à aucun calcul ; la partie prospective est qualitative et "
        "sourcée, sans aucun chiffre nouveau ; signale ce qui manque, n'invente rien."
    )
    return "\n\n".join([
        "Tu es analyste à la Cellule des Statistiques du MINPMEESA. Rédige, dans "
        "le registre institutionnel, une NOTE D'ANALYSE DE PERSPECTIVE destinée "
        "aux décideurs, pour éclairer la prise de décision.",
        regles,
        f"CHIFFRES-CLÉS (exercice {ctx.exercice}, seuls citables) :\n{figures}",
        f"SIGNAUX DE CONJONCTURE (à synthétiser, sans reprendre les valeurs) :\n{tendances}",
        f"MODÈLES DE FORME (notes de perspective existantes) :\n{patrons}",
        "STRUCTURE ATTENDUE : 1) Situation d'ensemble ; 2) Dynamiques et signaux ; "
        "3) Points d'attention ; 4) Perspectives et pistes de décision. "
        "Produis des propositions courtes préfixées « - ».",
        regles,
    ])


# --------------------------------------------------------------------------- #
#  Génération
# --------------------------------------------------------------------------- #
def _note_extractive(ctx: ContextePerspective) -> str:
    lignes = [f"# Note d'analyse de perspective — exercice {ctx.exercice}", "",
              "## 1. Situation d'ensemble (chiffres-clés)"]
    for enonce in ctx.figures[:12]:
        import re
        m = re.match(r"(.*?)\s*=\s*(.+)$", enonce)
        if m:
            lignes.append(f"- {m.group(1).strip()} : {m.group(2).strip()}.")
    lignes += ["", "## 2. Dynamiques et signaux de conjoncture"]
    for t in ctx.tendances[:3]:
        forme = _sans_nombres(t)
        if len(forme) > 30:
            lignes.append(f"- {forme[:300]}")
    lignes += ["", "## 3. Perspectives et pistes de décision"]
    for p in ctx.patrons[:2]:
        forme = _sans_nombres(p)
        if len(forme) > 30:
            lignes.append(f"- {forme[:300]}")
    return "\n".join(lignes)


def generer_note(store: Store, exercice: int, seed: int = 42) -> NotePerspective:
    ctx = assembler_contexte(store, exercice)
    note = NotePerspective(exercice=exercice, sources=ctx.sources)
    if not ctx.figures:
        note.texte = ("Abstention : chiffres-clés indisponibles pour l'exercice "
                      f"{exercice} ; aucune note de perspective ne peut être fondée.")
        note.audit = controler_propositions([], "")
        return note

    base, model = _llm_config()
    texte = None
    if base and model:
        texte = _appel_llm(construire_prompt(ctx), base, model, seed=seed, max_tokens=900)
        if texte is not None:
            note.regime = f"référence (llm:{model})"
    if texte is None:
        texte = _note_extractive(ctx)

    props = parser_propositions(texte, source_id="perspective")
    audit = controler_propositions(props, ctx.bloc_donnees())
    # On conserve les propositions retenues (les valeurs non sourcées sont écartées).
    note.propositions = [a.proposition for a in audit.retenues]
    note.audit = audit
    note.texte = texte
    return note
