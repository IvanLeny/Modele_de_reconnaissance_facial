"""
Construction de l'instruction de génération (cahier des charges, Étape 6.1).

Instruction en **cinq blocs**, dans cet ordre :
  1. rôle assigné ;
  2. règles de restitution ;
  3. bloc de données (les trois blocs de contexte étiquetés) ;
  4. bloc d'exemples (commentaires antérieurs = patron de rédaction) ;
  5. consigne de sortie.

Les **règles de restitution sont répétées après le bloc d'exemples** (biais
d'attention positionnelle : le modèle suit mieux la dernière consigne lue).
"""
from __future__ import annotations

from ..retrieval.context import Contexte

ROLE = (
    "Tu es un rédacteur de la Cellule des Statistiques du MINPMEESA. Tu rédiges, "
    "dans le registre institutionnel de la publication, le commentaire d'analyse "
    "d'un indicateur, à partir des seules données fournies."
)

REGLES = (
    "RÈGLES DE RESTITUTION (impératives) :\n"
    "1. N'emploie QUE les valeurs du bloc « VALEURS DE L'EXERCICE ». Aucune autre.\n"
    "2. Ne reprends AUCUNE valeur chiffrée des commentaires antérieurs.\n"
    "3. Ne procède à AUCUN calcul (pas de somme, moyenne, écart, taux dérivé).\n"
    "4. Si une information manque, signale-le ; n'invente rien.\n"
    "5. Reprends la FORME et le style des commentaires antérieurs, pas leurs chiffres."
)

CONSIGNE_SORTIE = (
    "CONSIGNE DE SORTIE : produis une liste de propositions, une par ligne, "
    "préfixée par « - ». Chaque proposition est une affirmation vérifiable "
    "indépendamment ; une phrase citant plusieurs valeurs donne autant de "
    "propositions. Rédige en français, de façon concise et neutre."
)


def construire_prompt(ctx: Contexte, intitule: str) -> str:
    """Assemble l'instruction complète (5 blocs, règles répétées à la fin)."""
    exemples = "\n".join(f"- {c}" for c in ctx.commentaires_anterieurs) or "(aucun exemple)"
    return "\n\n".join([
        ROLE,                                                   # bloc 1
        REGLES,                                                 # bloc 2
        f"INDICATEUR : {intitule}\n\nDONNÉES ET CONTEXTE :\n{ctx.rendu()}",  # bloc 3
        f"EXEMPLES (commentaires antérieurs, à imiter dans la FORME) :\n{exemples}",  # bloc 4
        CONSIGNE_SORTIE,                                        # bloc 5
        REGLES,                                                 # répétition (biais de position)
    ])
