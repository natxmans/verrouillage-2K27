@echo off
chcp 65001 >nul
echo ===================================================================
echo   Creation d'un raccourci de lancement pour UN poste
echo   A executer SUR CHAQUE PC du SAJ, une fois VerrouPoste.exe copie
echo   dans le meme dossier que ce fichier.
echo ===================================================================
echo.

if not exist "%~dp0VerrouPoste.exe" (
    echo [ERREUR] VerrouPoste.exe est introuvable a cote de ce fichier.
    echo Copie d'abord VerrouPoste.exe dans ce meme dossier, puis relance.
    pause
    exit /b 1
)

set /p NOM_POSTE=Nom exact du poste (ex: Poste 1) :

if "%NOM_POSTE%"=="" (
    echo Aucun nom saisi, operation annulee.
    pause
    exit /b 1
)

(
    echo @echo off
    echo cd /d "%%~dp0"
    echo start "" "VerrouPoste.exe" "%NOM_POSTE%"
) > "%~dp0Lancer - %NOM_POSTE%.bat"

echo.
echo ===================================================================
echo   Cree : "Lancer - %NOM_POSTE%.bat"
echo   Double-clique dessus pour demarrer le verrouillage de ce poste.
echo   (Tu peux aussi le mettre dans le dossier Demarrage de Windows
echo    pour qu'il se lance tout seul a l'allumage du PC.)
echo ===================================================================
pause
