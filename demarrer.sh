#!/usr/bin/env bash
# ====================================================================
#  Lanceur de l'assistant de rédaction des commentaires - MINPMEESA
#  Usage :  bash demarrer.sh
# ====================================================================
set -e
cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  Assistant de rédaction des commentaires - MINPMEESA"
echo "============================================================"
echo

PY="${PYTHON:-python3}"

# --- 1) Dépendances (une seule fois) ---
if [ ! -f "installation_ok.txt" ]; then
    echo "[1/2] Installation des dépendances Python..."
    "$PY" -m pip install -r requirements.txt
    echo ok > installation_ok.txt
else
    echo "[1/2] Dépendances déjà installées."
fi

# --- 2) Application web (système src/) ---
echo "[2/2] Ouverture de l'application dans votre navigateur..."
echo "      Le corpus est déjà inclus dans data/corpus/ ; rien à construire."
echo "      Pour arrêter : Ctrl+C."
echo
"$PY" -m streamlit run src/app/main.py
