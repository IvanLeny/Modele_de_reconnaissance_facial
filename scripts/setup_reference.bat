@echo off
REM =====================================================================
REM  INSTALLATION PROPRE ET ISOLEE de la configuration de reference (Windows)
REM  Demarche §3. A lancer dans l'Anaconda Prompt, UNE fois.
REM
REM     scripts\setup_reference.bat
REM
REM  Tout est installe dans un environnement conda DEDIE (rag_minpmeesa).
REM  Votre Anaconda de base n'est PAS modifie : Streamlit et vos autres
REM  projets restent intacts. Si quelque chose se passe mal, il suffit de
REM  supprimer cet environnement (conda env remove -n rag_minpmeesa).
REM =====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

set "ENV=rag_minpmeesa"
set "ENCODER=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
set "RERANKER=cross-encoder/ms-marco-MiniLM-L-6-v2"
if "%RAG_SETUP_LLM%"=="" set "RAG_SETUP_LLM=llama3.1:8b"

echo.
echo ==== 1/5 - Creation de l'environnement isole "%ENV%" (Python 3.11) ====
call conda create -y -n %ENV% python=3.11
REM (si l'environnement existe deja, on continue sans erreur)

echo.
echo ==== 2/5 - Activation de l'environnement ====
call conda activate %ENV%
if errorlevel 1 goto :erreur_env

echo.
echo ==== 3/5 - Installation des dependances (dans %ENV% uniquement) ====
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :erreur
python -m pip install "fastembed>=0.3" "sentence-transformers>=2.2"
if errorlevel 1 goto :erreur

echo.
echo ==== 4/5 - Pre-telechargement des modeles de reference ====
python scripts\_cache_modeles.py "%ENCODER%" "%RERANKER%"
if errorlevel 1 goto :erreur

echo.
echo ==== 5/5 - LLM local (Ollama) ====
set "OLLAMA=ollama"
where ollama >nul 2>nul
if errorlevel 1 (
    echo   Ollama absent - installation via winget...
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    REM Apres installation, ollama n'est pas encore dans le PATH de cette fenetre :
    REM on utilise directement son emplacement d'installation.
    set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
)
echo   Recuperation du modele : %RAG_SETUP_LLM%
"%OLLAMA%" pull %RAG_SETUP_LLM%
if errorlevel 1 echo   (Si erreur : ouvrez l'application Ollama une fois, puis relancez ce script.)

echo.
echo =====================================================================
echo  TERMINE. L'environnement isole "%ENV%" est pret.
echo.
echo  Pour LANCER l'evaluation en configuration de reference, double-cliquez
echo  sur scripts\lancer_reference.bat  (ou lancez-le dans l'Anaconda Prompt).
echo  Aucun fichier a editer a la main.
echo =====================================================================
goto :fin

:erreur_env
echo.
echo *** Impossible d'activer l'environnement conda. Etes-vous bien dans
echo     l'Anaconda Prompt ? Copiez le message ci-dessus et envoyez-le. ***
goto :fin

:erreur
echo.
echo *** Une erreur s'est produite pendant l'installation. Copiez le
echo     message ci-dessus et envoyez-le. ***

:fin
pause
endlocal
