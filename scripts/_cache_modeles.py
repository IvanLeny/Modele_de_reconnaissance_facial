"""
Amorçage du cache des modèles de référence (appelé par setup_modeles.bat / .sh).

Télécharge et met en cache l'encodeur transformeur et le cross-encodeur passés
en arguments. Aucune donnée du corpus ne transite : seuls les poids publics des
modèles sont récupérés. Sort avec un code non nul en cas d'échec (utile aux
scripts appelants).
"""
from __future__ import annotations

import sys


def cache_encoder(name: str) -> None:
    print(f"  · encodeur : {name}")
    try:
        from fastembed import TextEmbedding
        m = TextEmbedding(name)
        v = next(iter(m.embed(["amorçage du cache"])))
        print(f"    OK (fastembed, dim={len(v)})")
        return
    except Exception as e:
        print(f"    fastembed a échoué ({type(e).__name__}) ; essai sentence-transformers…")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(name)
    print("    OK (sentence-transformers)")


def cache_reranker(name: str) -> None:
    print(f"  · rerank   : {name}")
    from sentence_transformers import CrossEncoder
    CrossEncoder(name)
    print("    OK (CrossEncoder)")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _cache_modeles.py <encodeur> <reranker>")
        return 2
    try:
        cache_encoder(sys.argv[1])
        cache_reranker(sys.argv[2])
    except Exception as e:
        print(f"  ÉCHEC : {type(e).__name__} : {e}")
        return 1
    print("  Caches de modèles prêts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
