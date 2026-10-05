# Installer le verrouillage sur un PC du SAJ

**5 minutes par PC, sans Python.** Le dossier à copier s'appelle `Installation PC` : il contient `VerrouPoste.exe` (le programme) et `creer_lanceur_poste.bat` (qui fabrique le raccourci de lancement). Il se copie par clé USB.

> Si tu n'as pas le dossier `Installation PC` : il se fabrique en double-cliquant sur `construire_exe.bat` (sur un PC qui a Python), voir la [fiche technique](FICHE_TECHNIQUE.md).

## Avant de commencer (une seule fois pour tout le festival)

1. Sur le [site de gestion](https://natxmans.github.io/verrouillage-2K27/), vérifie le **nom de chaque poste** : « Poste 1 », « Poste 2 »… Le nom tapé sur le PC doit être **identique** (majuscules, espaces, accents).
2. Chaque PC doit avoir **internet** (wifi ou câble) : c'est comme ça qu'il reçoit les pauses.

## Sur chaque PC

1. Copie le dossier sur le PC (clé USB), par exemple dans `C:\Verrouillage2K27`.
2. Double-clique sur **`creer_lanceur_poste.bat`**, tape le **nom exact du poste** (ex : `Poste 1`) puis Entrée. Ça crée `Lancer - Poste 1.bat`.
3. Double-clique sur **`Lancer - Poste 1.bat`** : le programme démarre en arrière-plan (aucune fenêtre, c'est normal).
4. Au premier démarrage, un fichier **`config.json`** apparaît à côté du programme. Ouvre-le avec le Bloc-notes et remplace les chemins `C:\CHEMIN\A\CONFIGURER\...` par les vrais emplacements des jeux **sur ce PC** (clic droit sur le raccourci du jeu → Propriétés → champ « Cible »). Un jeu non renseigné fonctionne quand même pour le blocage et le chrono ; seul le lancement / la fermeture automatique du jeu est désactivé. Arrête puis relance le programme pour que ce soit pris en compte.
5. Pour qu'il démarre tout seul à l'allumage : touches **Windows + R**, tape `shell:startup`, Entrée, et glisse dedans un raccourci vers `Lancer - Poste 1.bat`.

## Pour tester

- Sur le site de gestion, **démarre une partie** sur le poste, puis clique **« Pause annonce »** : l'écran du PC doit se verrouiller (bandeau PAUSE), puis se débloquer à la reprise.
- Un bandeau **orange** « Poste … introuvable sur le site » en haut de l'écran signifie que le nom ne correspond pas : recrée le lanceur avec le bon nom.
- Test sans bloquer le clavier : dans une invite de commandes, dans le dossier, tape `VerrouPoste.exe "Poste 1" --sans-blocage`.

## Arrêter le programme

- **Ctrl + Maj + Q**, puis le mot de passe `2K27` (le K en majuscule).
- Ctrl + Alt + Suppr reste toujours disponible.

## Si Windows ou l'antivirus proteste

- « Windows a protégé votre ordinateur » : clique **« Informations complémentaires »** puis **« Exécuter quand même »**. Ça ne se redemande qu'une fois par PC.
- Un antivirus peut bloquer le programme (il bloque Alt+Tab, donc il ressemble à un logiciel espion) : ajoute `VerrouPoste.exe` aux **exclusions** de l'antivirus du PC.

## En cas de souci

Le fichier **`verrou_poste_log.txt`** (à côté du programme) note tout ce qui se passe. Les lignes importantes :

| Ligne | Sens |
|---|---|
| `Connexion Firebase etablie` | tout va bien |
| `Authentification anonyme Firebase impossible` | le PC n'a pas internet, ou un pare-feu bloque Google |
| `Poste … INTROUVABLE sur le site` | mauvais nom de poste |

## Switch et PS4

Rien à installer : ces consoles n'ont pas de verrouillage. On ouvre `https://natxmans.github.io/verrouillage-2K27/verrouillage.html?poste=Switch%201` (avec le nom exact du poste) sur un appareil relié au projecteur de la console, et on bascule l'entrée du projecteur pendant les annonces.

## Important

Si `verrou_poste.py` est modifié un jour, il faut **refabriquer `VerrouPoste.exe`** (double-clic sur `construire_exe.bat`, sur le PC qui a Python) puis recopier le nouveau `.exe` sur les PC.
