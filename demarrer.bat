@echo off
REM ====================================================================
REM  Lanceur unique de l'application RAG MINPMEESA (Windows)
REM  Double-cliquez ce fichier, ou tapez  demarrer.bat  dans le dossier.
REM  Il installe les dependances (1re fois), construit l'index (1re fois)
REM  puis ouvre l'application dans votre navigateur.
REM ====================================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo ============================================================
echo   Assistant documentaire RAG - MINPMEESA
echo ============================================================
echo.

REM --- 1) Installation des dependances (une seule fois) ---
if not exist "installation_ok.txt" (
    echo [1/3] Installation des dependances Python...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   ECHEC de l'installation. Verifiez votre connexion internet
        echo   puis relancez ce fichier.
        echo.
        pause
        exit /b 1
    )
    echo ok> installation_ok.txt
) else (
    echo [1/3] Dependances deja installees.
)

REM --- 2) Construction de l'index (une seule fois) ---
if not exist "data\index\chunks.jsonl" (
    echo [2/3] Construction de l'index a partir du corpus ^(1 a 2 minutes^)...
    python -m rag_minpmeesa.app.cli build
    if errorlevel 1 (
        echo   ECHEC de la construction de l'index.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Index deja construit.
)

REM --- 3) Lancement de l'application web ---
echo [3/3] Ouverture de l'application dans votre navigateur...
echo.
echo   Pour arreter l'application : revenez ici et appuyez sur Ctrl+C.
echo.
python -m streamlit run rag_minpmeesa\app\streamlit_app.py

pause
