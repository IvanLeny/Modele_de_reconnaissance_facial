@echo off
REM ====================================================================
REM  Lanceur de l'assistant de redaction des commentaires - MINPMEESA
REM  Double-cliquez ce fichier, ou tapez  demarrer.bat  dans le dossier.
REM  Il installe les dependances (1re fois) puis ouvre l'application.
REM ====================================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo ============================================================
echo   Assistant de redaction des commentaires - MINPMEESA
echo ============================================================
echo.

REM --- 1) Installation des dependances (une seule fois) ---
if not exist "installation_ok.txt" (
    echo [1/2] Installation des dependances Python...
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
    echo [1/2] Dependances deja installees.
)

REM --- 2) Lancement de l'application web (systeme src/) ---
echo [2/2] Ouverture de l'application dans votre navigateur...
echo.
echo   Le corpus est deja inclus dans data\corpus\ ; rien a construire.
echo   Pour arreter l'application : revenez ici et appuyez sur Ctrl+C.
echo.
python -m streamlit run src\app\main.py

pause
