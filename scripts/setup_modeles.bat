@echo off
REM =====================================================================
REM  Installation cle en main de la CONFIGURATION DE REFERENCE (Windows)
REM  Demarche §3. A lancer dans l'Anaconda Prompt (ou double-clic), UNE fois,
REM  sur une machine avec acces internet.
REM
REM     scripts\setup_modeles.bat
REM
REM  Etapes :
REM    1. installe les bibliotheques de modeles ;
REM    2. pre-telecharge les caches des modeles de reference (encodeur + rerank) ;
REM    3. installe Ollama (via winget) si absent et recupere le LLM local ;
REM    4. rappelle les etapes suivantes.
REM =====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

set "ENCODER=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
set "RERANKER=cross-encoder/ms-marco-MiniLM-L-6-v2"
if "%RAG_SETUP_LLM%"=="" set "RAG_SETUP_LLM=llama3.1:8b"

echo.
echo ==== 1/4 - Installation des bibliotheques de modeles ====
python -m pip install --upgrade "fastembed>=0.3" "sentence-transformers>=2.2"
if errorlevel 1 goto :erreur

echo.
echo ==== 2/4 - Pre-telechargement des caches de modeles ====
python scripts\_cache_modeles.py "%ENCODER%" "%RERANKER%"
if errorlevel 1 goto :erreur

echo.
echo ==== 3/4 - LLM local (Ollama) ====
where ollama >nul 2>nul
if errorlevel 1 (
    echo   Ollama absent - installation via winget...
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    echo   Si winget est indisponible, telechargez OllamaSetup.exe sur https://ollama.com/download
) else (
    echo   Ollama deja installe.
)
echo   Recuperation du modele : %RAG_SETUP_LLM%
ollama pull %RAG_SETUP_LLM%
if errorlevel 1 echo   (Si erreur : ouvrez l'application Ollama une fois, puis relancez ce script.)

echo.
echo ==== 4/4 - Etapes suivantes (a faire a la main) ====
echo   a) Dans config.yaml :
echo        embedding:
echo          backend: "transformer"
echo        restitution:
echo          synthesis: "llm"
echo          llm_base_url: "http://localhost:11434/v1"
echo          llm_model: "%RAG_SETUP_LLM%"
echo.
echo   b) Reconstruire l'index :   python -m rag_minpmeesa.app.cli build
echo   c) Verifier :               python -m rag_minpmeesa.app.cli doctor
echo.
echo ==== Termine. ====
goto :fin

:erreur
echo.
echo *** Une erreur s'est produite. Copiez le message ci-dessus et envoyez-le. ***

:fin
pause
endlocal
