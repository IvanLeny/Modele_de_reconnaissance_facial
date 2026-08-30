"""
Interface en ligne de commande (chapitre 3.7).

Commandes :
    build            construit (ou reconstruit) l'index à partir du corpus.
    query "…"        interroge le système et affiche la réponse sourcée.
    eval             exécute le protocole d'évaluation complet (chapitre 4).
    info             affiche l'état de l'index et la configuration.

Exemples :
    python -m rag_minpmeesa.app.cli build
    python -m rag_minpmeesa.app.cli query "trésorerie des PME au T2 2024" --mode production
    python -m rag_minpmeesa.app.cli query "croissance mondiale T3 2024" --mode consultation
    python -m rag_minpmeesa.app.cli eval
"""
from __future__ import annotations

import argparse
import sys

from ..config import Mode, get_settings
from ..engine import RAGEngine


def _print_answer(ans) -> None:
    print("\n" + "=" * 78)
    print(f"MODE : {ans.mode}   |   MÉTHODE : {ans.synthesis_method}")
    print("=" * 78)
    if ans.refused:
        print(ans.message)
        return
    print("\nSYNTHÈSE (données chiffrées reprises littéralement des sources) :\n")
    for s in ans.sentences:
        print(f"  • {s.text}  {s.citation}")
    print("\nPASSAGES SOURCES :")
    for b in ans.context:
        print(f"  [{b.sid}] {b.citation}")
        extract = b.text[:200].replace("\n", " ")
        print(f"       {extract}…")
    print("\nCONTRÔLES QUALITÉ :")
    print(f"  - Exactitude chiffrée : {ans.numeric_audit.accuracy:.2f} "
          f"({ans.numeric_audit.supported}/{ans.numeric_audit.total} nombres sourcés)")
    if ans.numeric_audit.unsupported:
        print(f"    ⚠ nombres non sourcés retirés : {ans.numeric_audit.unsupported}")
    print(f"  - Fidélité : {ans.faithfulness.faithfulness:.2f} "
          f"({ans.faithfulness.n_supported}/{ans.faithfulness.n_sentences} énoncés soutenus)")


def cmd_build(args):
    eng = RAGEngine(verbose=True)
    print("Construction de l'index…")
    eng.build_index()
    print("Index construit et enregistré.")


def cmd_query(args):
    eng = RAGEngine().load_index()
    ans = eng.query(args.text, mode=Mode(args.mode))
    _print_answer(ans)


def cmd_eval(args):
    from ..evaluation.run_eval import run_full_evaluation
    eng = RAGEngine().ensure_ready()
    run_full_evaluation(eng, verbose=True)


def cmd_info(args):
    settings = get_settings()
    eng = RAGEngine()
    try:
        eng.load_index()
        print("Index :", eng.store.meta)
    except FileNotFoundError:
        print("Index non construit. Lancez : python -m rag_minpmeesa.app.cli build")
    print("Corpus :", settings.paths.corpus_dir)
    print("Modes  :", [m.value for m in Mode])


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="rag_minpmeesa",
        description="Système RAG hybride MINPMEESA (mémoire Adnane MAMA IDISSA).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="construire l'index").set_defaults(func=cmd_build)

    q = sub.add_parser("query", help="interroger le système")
    q.add_argument("text", help="la question")
    q.add_argument("--mode", choices=[m.value for m in Mode],
                   default=Mode.PRODUCTION.value)
    q.set_defaults(func=cmd_query)

    sub.add_parser("eval", help="évaluation complète").set_defaults(func=cmd_eval)
    sub.add_parser("info", help="état de l'index").set_defaults(func=cmd_info)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
