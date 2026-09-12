"""
Calibration du seuil d'abstention (démarche §5).

Le système doit « savoir ne pas répondre ». On calibre le seuil de confiance
(meilleur score de fusion) sur un ensemble équilibré de requêtes :
  - EN PÉRIMÈTRE : questions du jeu de test annoté (le système DOIT répondre) ;
  - HORS PÉRIMÈTRE : questions sur des sujets absents du corpus, rédigées
    indépendamment de celui-ci (le système DOIT s'abstenir).

Pour chaque seuil candidat, on décide « abstention si meilleur score < seuil »
et on mesure la qualité de cette décision binaire (une abstention est correcte
sur une requête hors périmètre, une réponse est correcte sur une requête en
périmètre). On retient le seuil qui maximise le J de Youden
(sensibilité + spécificité − 1), robuste au déséquilibre des classes.

Sortie : outputs/runs/calibration_<horodatage>/calibration_abstention.csv
et un résumé JSON avec le seuil recommandé. La courbe 300 dpi est tracée à
l'étape 9 à partir de ce CSV.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from ..config import Mode, get_settings
from ..engine import RAGEngine
from ..retrieval.pipeline import CONFIGS
from .gold import load_gold


def _load_out_of_scope(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["questions"])


def _confidence(hits) -> float:
    """Confiance de récupération = meilleur score lexical (BM25) des passages.

    C'est le signal d'abstention retenu : contrairement au score de fusion
    normalisé (toujours proche de 1 en tête, donc non discriminant), le BM25
    brut mesure le recouvrement absolu avec le vocabulaire métier du corpus.
    """
    lex = [h.score_lexical for h in hits if h.score_lexical is not None]
    return max(lex) if lex else 0.0


def _top_scores(engine: RAGEngine) -> Tuple[List[float], List[float]]:
    """Confiance lexicale pour chaque requête en / hors périmètre.

    On utilise la configuration de production (hybride + reranking) et le mode
    de chaque question ; les requêtes hors périmètre passent en production
    (corpus le plus large) — c'est le cas le plus défavorable pour l'abstention.
    """
    settings = get_settings()
    gold = load_gold()
    run = CONFIGS["hybride+rerank"]

    in_scope: List[float] = []
    for q in gold:
        hits = engine.retrieve(q.question, mode=q.mode, run=run, top_k=5)
        in_scope.append(_confidence(hits))

    oos_path = settings.paths.gold_dir / "hors_perimetre.json"
    out_scope: List[float] = []
    for question in _load_out_of_scope(oos_path):
        hits = engine.retrieve(question, mode=Mode.PRODUCTION, run=run, top_k=5)
        out_scope.append(_confidence(hits))
    return in_scope, out_scope


def _decision_quality(threshold: float, in_scope: List[float],
                      out_scope: List[float]) -> Dict[str, float]:
    """Qualité de la règle « abstention si meilleur score < seuil ».

    Convention : la classe positive est « hors périmètre » (il faut s'abstenir).
      - vrai positif  : requête hors périmètre correctement refusée ;
      - vrai négatif  : requête en périmètre correctement traitée.
    """
    tp = sum(1 for s in out_scope if s < threshold)     # hors périmètre, abstenu
    fn = len(out_scope) - tp                             # hors périmètre, répondu (fuite)
    tn = sum(1 for s in in_scope if s >= threshold)      # en périmètre, répondu
    fp = len(in_scope) - tn                              # en périmètre, abstenu à tort

    sensibilite = tp / len(out_scope) if out_scope else 0.0      # rappel des refus
    specificite = tn / len(in_scope) if in_scope else 0.0        # taux de réponses gardées
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * sensibilite / (precision + sensibilite)
          if (precision + sensibilite) else 0.0)
    youden = sensibilite + specificite - 1.0
    return {
        "seuil": round(threshold, 5),
        "abstentions_correctes": tp,
        "reponses_perdues": fp,
        "fuites_hors_perimetre": fn,
        "reponses_gardees": tn,
        "sensibilite_refus": round(sensibilite, 4),
        "specificite_reponse": round(specificite, 4),
        "precision_refus": round(precision, 4),
        "f1_refus": round(f1, 4),
        "youden_j": round(youden, 4),
    }


def run_calibration(verbose: bool = True) -> Path:
    settings = get_settings()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = settings.paths.runs_dir / f"calibration_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    engine = RAGEngine().ensure_ready()
    in_scope, out_scope = _top_scores(engine)
    if verbose:
        print(f"  {len(in_scope)} requêtes en périmètre, "
              f"{len(out_scope)} hors périmètre.")

    # Grille de seuils entre les deux distributions de scores.
    lo = min(in_scope + out_scope + [0.0])
    hi = max(in_scope + out_scope + [0.001])
    grid = [lo + (hi - lo) * i / 40 for i in range(41)]

    rows = [_decision_quality(t, in_scope, out_scope) for t in grid]
    fields = list(rows[0].keys())
    with open(out / "calibration_abstention.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)

    # Seuil recommandé : J de Youden maximal ; en cas d'égalité, le plus petit
    # seuil (favorise le rappel — on préfère répondre quand la confiance suffit).
    best = max(rows, key=lambda r: (r["youden_j"], -r["seuil"]))
    summary = {
        "n_en_perimetre": len(in_scope),
        "n_hors_perimetre": len(out_scope),
        "score_min_en_perimetre": round(min(in_scope), 5) if in_scope else None,
        "score_max_hors_perimetre": round(max(out_scope), 5) if out_scope else None,
        "seuil_courant": settings.abstention.min_lexical_score,
        "seuil_recommande": best["seuil"],
        "qualite_au_seuil_recommande": best,
    }
    (out / "calibration_resume.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"  Seuil courant   : {summary['seuil_courant']}")
        print(f"  Seuil recommandé: {summary['seuil_recommande']} "
              f"(J={best['youden_j']}, fuites={best['fuites_hors_perimetre']}, "
              f"réponses perdues={best['reponses_perdues']})")
        print(f"  Calibration écrite dans {out}")
    return out


if __name__ == "__main__":
    run_calibration()
