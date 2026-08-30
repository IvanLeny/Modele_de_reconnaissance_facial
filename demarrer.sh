#!/usr/bin/env bash
# ====================================================================
#  Lanceur unique de l'application RAG MINPMEESA (macOS / Linux)
#  Usage :  bash demarrer.sh
# ====================================================================
set -e
cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  Assistant documentaire RAG - MINPMEESA"
echo "============================================================"
echo

PY="${PYTHON:-python3}"

# --- 1) Dépendances (une seule fois) ---
if [ ! -f "installation_ok.txt" ]; then
    echo "[1/3] Installation des dépendances Python..."
    "$PY" -m pip install -r requirements.txt
    echo ok > installation_ok.txt
else
    echo "[1/3] Dépendances déjà installées."
fi

# --- 2) Index (une seule fois) ---
if [ ! -f "data/index/chunks.jsonl" ]; then
    echo "[2/3] Construction de l'index à partir du corpus (1 à 2 minutes)..."
    "$PY" -m rag_minpmeesa.app.cli build
else
    echo "[2/3] Index déjà construit."
fi

# --- 3) Application web ---
echo "[3/3] Ouverture de l'application dans votre navigateur..."
echo "      Pour arrêter : Ctrl+C."
echo
"$PY" -m streamlit run rag_minpmeesa/app/streamlit_app.py
