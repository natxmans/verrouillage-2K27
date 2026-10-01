@echo off
chcp 65001 >nul
echo ===================================================================
echo   Fabrication de VerrouPoste.exe (version autonome, sans Python)
echo   A executer UNE SEULE FOIS, sur TON PC (celui qui a Python)
echo ===================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas trouve sur ce PC.
    echo Ce script doit etre lance sur le PC qui a Python d'installe.
    pause
    exit /b 1
)

echo Installation / mise a jour des outils necessaires...
python -m pip install --upgrade pyinstaller pillow
if errorlevel 1 (
    echo [ERREUR] L'installation a echoue. Verifie ta connexion internet.
    pause
    exit /b 1
)

echo.
echo Compilation en cours (peut prendre 1 a 2 minutes)...
python -m PyInstaller --onefile --noconsole --name VerrouPoste --clean verrou_poste.py
if errorlevel 1 (
    echo [ERREUR] La compilation a echoue, voir le message ci-dessus.
    pause
    exit /b 1
)

echo.
echo ===================================================================
echo   TERMINE !
echo   Le programme autonome se trouve ici :
echo   dist\VerrouPoste.exe
echo.
echo   C'est CE fichier (et uniquement celui-la) qu'il faut copier sur
echo   les PC du SAJ. Aucune installation de Python n'y est necessaire.
echo ===================================================================
pause
