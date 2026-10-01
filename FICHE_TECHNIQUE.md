# Fiche technique — Déployer le verrouillage sur les PC du SAJ (sans Python)

## Le problème

`verrou_poste.py` est le programme complet (écran de pause, blocage Alt+Tab et
touche Windows, chronomètre, lancement/fermeture automatique du jeu). Il est
écrit en Python — mais les PC du SAJ n'ont pas Python installé, et on ne peut
pas en installer sur chacun d'eux.

## La solution : un seul fichier .exe, aucune installation

On transforme `verrou_poste.py` en un programme autonome (`VerrouPoste.exe`)
qui contient déjà tout ce qu'il faut pour fonctionner (y compris Python
lui-même, invisible à l'intérieur). On ne fait ça **qu'une seule fois**, sur
TON PC (celui qui a Python 3.14.6). Ensuite, ce fichier `.exe` se copie tel
quel sur n'importe quel PC Windows, même sans Python — exactement comme un
jeu ou un logiciel normal.

---

## Étape 1 — Fabriquer le .exe (sur ton PC, une seule fois)

1. Ouvre le dossier du projet (`verrouillage-2k27`) sur ton PC.
2. Double-clique sur **`construire_exe.bat`**.
3. Laisse-le travailler (1 à 2 minutes). Il installe automatiquement les
   outils nécessaires (PyInstaller, Pillow) puis fabrique le programme.
4. À la fin, le fichier recherché est : **`dist\VerrouPoste.exe`**.

C'est ce fichier unique qu'il faut maintenant diffuser sur les PC du SAJ.

---

## Étape 2 — Préparer la clé USB (ou le dossier à copier)

Prépare un dossier (sur clé USB par exemple) contenant uniquement :

- `VerrouPoste.exe` (fabriqué à l'étape 1)
- `creer_lanceur_poste.bat`

(Pas besoin d'emporter Python, ni `verrou_poste.py`, ni rien d'autre.)

---

## Étape 3 — Installer sur chaque PC du SAJ

Sur **chaque** PC du SAJ :

1. Crée un dossier, par exemple `C:\Verrouillage2K27`.
2. Copie dedans `VerrouPoste.exe` et `creer_lanceur_poste.bat`.
3. Double-clique sur `creer_lanceur_poste.bat` et tape le nom exact du poste
   (celui utilisé dans `gestion-parties.html`, ex: `Poste 1`).
   → Ça crée un fichier `Lancer - Poste 1.bat` dans le même dossier.
4. Double-clique sur ce `Lancer - Poste 1.bat` pour démarrer le verrouillage.

**Pour qu'il démarre tout seul à l'allumage du PC** (recommandé) :
- Appuie sur `Windows + R`, tape `shell:startup`, Entrée.
- Fais un raccourci de `Lancer - Poste 1.bat` dans ce dossier qui s'ouvre.

Chaque poste n'a besoin que de sa propre copie de `VerrouPoste.exe` (ou d'une
copie partagée + son propre `Lancer - ....bat`, peu importe).

---

## Les chemins des jeux (une fois par PC)

Au premier lancement, `VerrouPoste.exe` crée automatiquement un fichier
`config.json` à côté de lui. Ouvre-le avec le Bloc-notes et remplace les
chemins par les vrais emplacements des jeux **sur ce PC précis** (clic droit
sur le raccourci du jeu → Propriétés → "Cible"). Un jeu non renseigné
continue de fonctionner pour le blocage/chrono, seul le lancement/fermeture
automatique ne s'applique pas à lui.

---

## Fonctionne sans aucune install, mais en version allégée

Si un poste pose problème (très vieux PC, Chromebook, tablette...), il reste
la solution de secours déjà en place : ouvrir dans un navigateur
`verrouillage.html?poste=Poste%201`. Aucune installation requise, mais cette
version affiche seulement l'écran de pause — elle ne bloque pas le clavier et
ne suspend pas le jeu.

---

## Si Windows affiche un avertissement au premier lancement

`VerrouPoste.exe` n'étant pas signé par un éditeur reconnu, Windows
SmartScreen peut afficher "Windows a protégé votre ordinateur". C'est normal
pour un programme fait maison :
→ Clique sur **"Informations complémentaires"**, puis **"Exécuter quand même"**.
Ça ne se redemande qu'une fois par PC.

---

## En cas de souci sur place

Un fichier `verrou_poste_log.txt` se crée automatiquement à côté de
`VerrouPoste.exe` et note tout ce qui se passe (démarrage, connexion
Firebase, jeu lancé/fermé, erreurs). Utile pour comprendre un problème sans
avoir besoin d'un terminal.

- Sortie d'urgence du programme : `Ctrl+Maj+Q` (demande le mot de passe `2K27`).
- `Ctrl+Alt+Suppr` reste toujours disponible, Windows l'autorise toujours.
