# Installation et exécution — assistant de rédaction des commentaires

Cible : **100 % local**, Ubuntu 24.04, Python 3.11, sans GPU. Deux régimes :
- **dégradé** (défaut, aucun modèle) : composition extractive déterministe +
  stockage SQLite. Toute la chaîne s'exécute et s'évalue hors ligne.
- **référence** : LLM local (Ollama) + PostgreSQL/pgvector. Aucun changement de
  code — seulement `config.yaml` et la présence des services.

## 1. Prérequis et dépendances

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # PyMuPDF, scikit-learn, scipy, matplotlib…
```

## 2. Exécuter la chaîne (mode dégradé, immédiat)

```bash
# Démonstration en 5 temps (référence, C0, 2 contrôles, abstention)
python -m src.app.cli demo
# Générer un commentaire pour un exercice
python -m src.app.cli generer --exercice 2023 --n 0
# Harnais d'évaluation complet (C0-C4 + baseline, 5 sorties CSV)
python -m src.eval.runner
# Statistiques + figures 300 dpi
python -m src.eval.stats
# Interface (3 espaces)
streamlit run src/app/main.py
# Tests
pytest tests/test_src_*.py -q
```

Sorties : `outputs/runs/generation_<horodatage>/` et `outputs/figures/`.

## 3. Passer en régime de référence (machine cible)

### 3.1 LLM local (Ollama)

```bash
# Installer Ollama, puis récupérer un modèle 7-8B francophone quantifié 4 bits
ollama pull llama3.1:8b
ollama serve                          # http://localhost:11434
export RAG_LLM_BASE_URL=http://localhost:11434/v1
export RAG_LLM_MODEL=llama3.1:8b
```

Le générateur bascule automatiquement en régime « référence (llm:…) » (paramètres
fixés : température 0,2, 700 jetons, graine). Sans point d'accès, il revient au
mode extractif. Réseau bloqué : transférer les caches (`~/.ollama/models/`,
`~/.cache/huggingface/`).

### 3.2 PostgreSQL + pgvector

```bash
sudo apt install postgresql postgresql-16-pgvector
sudo -u postgres psql -c "CREATE DATABASE minpmeesa;"
sudo -u postgres psql -d minpmeesa -f db/schema.sql   # crée l'extension vector + le schéma
```

Le développement et les tests utilisent SQLite (même schéma logique) ; sur la
machine cible, `db/schema.sql` crée le schéma PostgreSQL. La bascule se fait par
`config.yaml` (section `storage`) sans modifier le code — le filtrage temporel
s'exprimant dans la clause `WHERE`, la même requête vaut pour les deux moteurs.

## 4. Reproductibilité

- Graine fixée (42) ; sorties d'évaluation horodatées.
- `run_metadata.json` de chaque run inscrit le **régime actif**, la graine, la
  plateforme et le nombre d'unités.
- Journal des difficultés et solutions : `docs/JOURNAL_NOUVEAU_PROTOTYPE.md`.
