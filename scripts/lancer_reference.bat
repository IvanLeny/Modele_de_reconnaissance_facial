@echo off
REM =====================================================================
REM  LANCEUR - configuration de reference (Windows), environnement isole.
REM  A lancer APRES scripts\setup_reference.bat.
REM
REM     scripts\lancer_reference.bat
REM
REM  Active l'environnement dedie, force la configuration de reference par
REM  variables d'environnement (aucun fichier config.yaml a modifier),
REM  reconstruit l'index avec l'encodeur transformeur, verifie l'etat des
REM  modeles, puis produit les resultats d'evaluation (harnais, stats, figures).
REM =====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

set "ENV=rag_minpmeesa"
if "%RAG_SETUP_LLM%"=="" set "RAG_SETUP_LLM=llama3.1:8b"

REM --- Configuration de reference activee UNIQUEMENT pour cette fenetre ---
set "RAG_EMBEDDING_BACKEND=transformer"
set "RAG_SYNTHESIS=llm"
set "RAG_LLM_BASE_URL=http://localhost:11434/v1"
set "RAG_LLM_MODEL=%RAG_SETUP_LLM%"

echo ==== Activation de l'environnement isole "%ENV%" ====
call conda activate %ENV%
if errorlevel 1 (
    echo *** Environnement "%ENV%" introuvable. Lancez d'abord scripts\setup_reference.bat ***
    pause
    goto :eof
)

echo.
echo ==== Diagnostic des modeles (doctor) ====
python -m rag_minpmeesa.app.cli doctor

echo.
echo ==== Reconstruction de l'index avec l'encodeur de reference ====
python -m rag_minpmeesa.app.cli build
if errorlevel 1 goto :erreur

echo.
echo ==== Evaluation : harnais C0-C5 ====
python -m rag_minpmeesa.app.cli harness
echo.
echo ==== Statistiques (Wilcoxon, Kendall, par categorie) ====
python -m rag_minpmeesa.app.cli stats
echo.
echo ==== Figures 300 dpi ====
python -m rag_minpmeesa.app.cli figures

echo.
echo =====================================================================
echo  TERMINE. Resultats dans outputs\runs\ et outputs\figures\.
echo  Envoyez-moi le contenu de ces dossiers pour l'integration au memoire.
echo =====================================================================
goto :fin

:erreur
echo.
echo *** Une erreur s'est produite. Copiez le message ci-dessus et envoyez-le. ***

:fin
pause
endlocal
