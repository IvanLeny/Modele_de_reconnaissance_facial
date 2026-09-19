"""
Interface en ligne de commande (démonstration et exploitation hors interface).

Commandes :
    demo           déroule le scénario de démonstration en cinq temps (Étape 10) ;
    generer …      génère le commentaire d'un indicateur pour un exercice.

La CLI n'a aucune logique propre : elle assemble contexte → génération →
garde-fous, comme l'interface Streamlit, et met en évidence les trois affichages
qui portent les garanties du dispositif (référence, proposition écartée,
abstention).
"""
from __future__ import annotations

import argparse

from ..ingestion.ingest import build_store
from ..retrieval.context import assembler_contexte
from ..generation.generate import generer
from ..guards.numeric import controler_propositions, Proposition
from ..guards.abstention import decider
from ..guards.provenance import tracer, SourceRef


def _afficher_audit(props, bloc_donnees, source: SourceRef):
    audit = controler_propositions(props, bloc_donnees)
    print(f"  Exactitude : {audit.exactitude:.2f} "
          f"({audit.n_valeurs_appariees}/{audit.n_valeurs} valeurs appariées)")
    for a in audit.retenues:
        t = tracer(a.proposition, source)
        marque = "•"
        print(f"   {marque} {a.proposition.texte}")
        print(f"       ↳ source : {t.source.libelle()} [{t.niveau}]")
    for a in audit.ecartees:
        print(f"   ✗ ÉCARTÉE (valeur non sourcée {a.valeurs_non_soutenues}) : "
              f"{a.proposition.texte}")
    return audit


def cmd_demo(args):
    store, ref = build_store(verbose=False)
    # Choix d'un indicateur réel bien doté (exercice 2023).
    unites = [k for k in ref.reference if k[0] == 2023]
    exercice, code = unites[0]
    intitule = ref.intitule[(exercice, code)]
    src = SourceRef(doc_id=f"annuaire_{exercice}", exercice=exercice, section="tableau apparié")

    print("=" * 78)
    print(f"SCÉNARIO DE DÉMONSTRATION — indicateur : {intitule[:70]}")
    print(f"Exercice traité : {exercice}")
    print("=" * 78)

    # Temps 1 : commentaire produit avec ses références (système complet).
    print("\n[1] COMMENTAIRE PRODUIT (ancré, avec références)")
    ctx = assembler_contexte(store, code, exercice, intitule=intitule)
    res = generer(ctx, intitule)
    print(f"  Régime : {res.regime}")
    _afficher_audit(res.propositions[:4], ctx.bloc_donnees(), src)

    # Temps 2 : le même sans ancrage documentaire (C0).
    print("\n[2] SANS ANCRAGE (C0 — données et intitulé seulement)")
    ctx0 = assembler_contexte(store, code, exercice, intitule=intitule)
    ctx0.commentaires_anterieurs = []
    res0 = generer(ctx0, intitule)
    print(f"  {len(res0.propositions)} propositions, sans réutilisation d'un patron de rédaction.")

    # Temps 3 : une valeur d'un commentaire ANTÉRIEUR, absente du bloc de données.
    print("\n[3] CONTRÔLE — valeur d'un commentaire antérieur écartée")
    faux = Proposition("Le stock de PME atteint 393 166 unités.", "commentaire_anterieur")
    _afficher_audit([faux], "Nombre de PME en 2023 : 393 175.", src)

    # Temps 4 : une valeur inventée.
    print("\n[4] CONTRÔLE — valeur inventée écartée")
    invente = Proposition("La croissance atteint 5,9 %.", "modele")
    _afficher_audit([invente], "Croissance de la zone CEMAC : 2,4 % en 2023.", src)

    # Temps 5 : abstention (indicateur sans données / sans contexte).
    print("\n[5] ABSTENTION — indicateur hors périmètre")
    d = decider(data_block="", commentaires_anterieurs=[], min_confiance=0.25,
                tableau_apparie=False)
    print(f"   ⚠ {d.motif}")
    print("=" * 78)


def cmd_perspective(args):
    """Produit une note d'analyse de perspective à partir de tout le corpus."""
    from ..retrieval.store import Store
    from ..ingestion.ingest import populate_all
    from ..generation.perspective import generer_note
    store = Store(":memory:")
    populate_all(store)
    note = generer_note(store, args.exercice)
    print("=" * 78)
    print(note.texte)
    print("=" * 78)
    if note.audit is not None:
        print(f"CONTRÔLE : exactitude {note.audit.exactitude:.2f} ; "
              f"{len(note.audit.ecartees)} proposition(s) écartée(s) par le garde-fou.")
    print("RÉGIME :", note.regime)
    print("SOURCES :", ", ".join(note.sources))


def cmd_generer(args):
    store, ref = build_store(verbose=False)
    cible = [k for k in ref.reference if k[0] == args.exercice]
    if not cible:
        print("Aucun indicateur pour cet exercice.")
        return
    exercice, code = cible[min(args.n, len(cible) - 1)]
    intitule = ref.intitule[(exercice, code)]
    ctx = assembler_contexte(store, code, exercice, intitule=intitule)
    res = generer(ctx, intitule)
    src = SourceRef(doc_id=f"annuaire_{exercice}", exercice=exercice)
    print(f"Indicateur : {intitule}\nExercice : {exercice}\nRégime : {res.regime}\n")
    _afficher_audit(res.propositions, ctx.bloc_donnees(), src)


def main(argv=None):
    p = argparse.ArgumentParser(prog="minpmeesa-gen",
                                description="Assistant de rédaction des commentaires MINPMEESA.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="scénario de démonstration en 5 temps").set_defaults(func=cmd_demo)
    g = sub.add_parser("generer", help="générer le commentaire d'un indicateur")
    g.add_argument("--exercice", type=int, default=2023)
    g.add_argument("--n", type=int, default=0, help="indice de l'indicateur")
    g.set_defaults(func=cmd_generer)
    pp = sub.add_parser("perspective", help="note d'analyse de perspective (aide à la décision)")
    pp.add_argument("--exercice", type=int, default=2023)
    pp.set_defaults(func=cmd_perspective)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
