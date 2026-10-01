"""
Ecran de verrouillage pour un poste du Festival 2K27 (façon Veyon).

Usage :
    python verrou_poste.py "Nom du poste"

Le programme lit en direct l'etat du poste dans la meme base Firebase que
l'outil web (gestion-parties.html). Quand ce poste passe en pause depuis
la tablette de controle, une fenetre plein ecran apparait ici et bloque
Alt+Tab / la touche Windows tant que la pause dure.

Sortie de secours, a tout moment : Ctrl+Maj+Q (ferme le programme).
Ctrl+Alt+Suppr reste toujours disponible (Windows l'autorise toujours).

En plus du blocage visuel, le jeu actif au moment de la pause est reellement
suspendu au niveau de Windows (toute son execution s'arrete, comme si le temps
etait fige pour lui) en utilisant directement les fonctions Windows (aucune
installation supplementaire necessaire, tout est deja inclus avec Python).

Apercu d'ecran a distance (facon Veyon, visible depuis gestion-parties.html,
bouton "Ecrans") : necessite Pillow (pip install pillow). Sans Pillow, tout le
reste du programme continue de fonctionner normalement, seul l'apercu est
desactive.

Configuration des jeux (chemins des .exe) : voir/modifier "config.json", cree
automatiquement a cote de ce fichier au premier lancement.

Journal : "verrou_poste_log.txt" (a cote de ce fichier) trace les evenements
utiles (demarrage, connexion/deconnexion Firebase, jeu lance/ferme, erreurs) --
utile pour diagnostiquer un souci sur place sans terminal.
"""
import sys
import os
import json
import ssl
import subprocess
import threading
import time
import traceback
import urllib.parse
import urllib.request
import tkinter as tk
import ctypes
import winsound
import base64
import io
from ctypes import wintypes

# Apercu d'ecran a distance (facon Veyon) : necessite Pillow (pip install pillow),
# seule dependance externe du projet. Sans elle, le reste du programme continue de
# fonctionner normalement, seul l'apercu d'ecran est desactive.
try:
    from PIL import ImageGrab
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False

DATABASE_URL = "https://festival2k27-default-rtdb.europe-west1.firebasedatabase.app"
FIREBASE_API_KEY = "AIzaSyCFd2YAtKt8efLtsQIeyvCr0B8rVBs7VZ0"

# Une fois transforme en .exe autonome (PyInstaller --onefile), __file__ pointe vers
# un dossier temporaire efface a chaque fermeture : config.json et le journal doivent
# plutot vivre a cote du vrai .exe (sys.executable), sinon ils seraient perdus a
# chaque relancement et semblaient "ne jamais se sauvegarder".
if getattr(sys, "frozen", False):
    DOSSIER_SCRIPT = os.path.dirname(os.path.abspath(sys.executable))
else:
    DOSSIER_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CHEMIN_CONFIG = os.path.join(DOSSIER_SCRIPT, "config.json")
CHEMIN_LOG = os.path.join(DOSSIER_SCRIPT, "verrou_poste_log.txt")


def journaliser(message):
    # Petit journal texte a cote du script : permet de diagnostiquer un souci une
    # fois lance en double-clic via le .bat (pas de terminal visible), sans acces a
    # distance. Best-effort comme le reste du programme : si l'ecriture echoue
    # (disque plein, dossier en lecture seule...), on continue sans planter.
    try:
        horodatage = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(CHEMIN_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{horodatage}] {message}\n")
    except Exception:
        pass


# Valeurs par defaut, utilisees tant qu'aucun config.json n'existe ou qu'il est
# invalide (degradation gracieuse, meme principe que le reste du programme).
JEUX_EXECUTABLES_DEFAUT = {
    "World of Padman": r"C:\CHEMIN\A\CONFIGURER\WorldOfPadman\wop.exe",
    "Trackmania": r"C:\CHEMIN\A\CONFIGURER\Trackmania\Trackmania.exe",
    "Fortnite": r"C:\CHEMIN\A\CONFIGURER\Fortnite\FortniteClient-Win64-Shipping.exe",
    "Valorant": r"C:\CHEMIN\A\CONFIGURER\VALORANT\live\VALORANT-Win64-Shipping.exe",
}


def charger_config_jeux():
    # A REMPLIR UNE FOIS PAR PC : plutot que de modifier ce fichier Python, on lit
    # maintenant les chemins des .exe depuis un simple config.json a cote du script
    # (cree automatiquement avec les valeurs par defaut s'il n'existe pas encore) --
    # n'importe qui peut l'ouvrir avec le Bloc-notes et remplacer les chemins, sans
    # toucher au code. Pour trouver un chemin : clic droit sur le raccourci du jeu >
    # Proprietes > "Cible". Un jeu absent de ce fichier (ou "Autre" saisi a la main)
    # ne sera simplement pas lance/ferme automatiquement, le reste (verrou, chrono,
    # suspension) continue de fonctionner normalement pour lui.
    if not os.path.exists(CHEMIN_CONFIG):
        try:
            with open(CHEMIN_CONFIG, "w", encoding="utf-8") as f:
                json.dump({"jeux_executables": JEUX_EXECUTABLES_DEFAUT}, f, ensure_ascii=False, indent=2)
            journaliser(f"config.json cree avec les valeurs par defaut ({CHEMIN_CONFIG})")
        except Exception as err:
            journaliser(f"Impossible de creer config.json : {err}")
        return dict(JEUX_EXECUTABLES_DEFAUT)
    try:
        with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)
        jeux_config = config.get("jeux_executables")
        if isinstance(jeux_config, dict) and jeux_config:
            journaliser(f"config.json charge ({len(jeux_config)} jeu(x))")
            return jeux_config
        journaliser("config.json present mais sans 'jeux_executables' valide - valeurs par defaut utilisees")
    except Exception as err:
        journaliser(f"config.json illisible ({err}) - valeurs par defaut utilisees")
    return dict(JEUX_EXECUTABLES_DEFAUT)


JEUX_EXECUTABLES = charger_config_jeux()

# Certains antivirus (Avast, etc.) interceptent le HTTPS pour le scanner avec leur
# propre certificat racine. Ce certificat est deja approuve par Windows (l'antivirus
# l'installe dans le magasin systeme) mais pas par le magasin separe de Python, d'ou
# une erreur de verification. On complete donc le contexte SSL de Python avec les
# certificats de confiance de Windows, au lieu de desactiver la verification.
def construire_contexte_ssl():
    contexte = ssl.create_default_context()
    try:
        for magasin in ("ROOT", "CA"):
            for cert, encodage, _ in ssl.enum_certificates(magasin):
                if encodage == "x509_asn":
                    try:
                        contexte.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert))
                    except ssl.SSLError:
                        pass
    except AttributeError:
        pass  # ssl.enum_certificates n'existe que sous Windows
    return contexte

CONTEXTE_SSL = construire_contexte_ssl()

# Solution de secours : sur certains PC, l'antivirus utilise un certificat mal forme
# que meme le magasin Windows ne suffit pas a faire accepter par Python (erreur
# "Basic Constraints of CA cert not marked critical"). Si ce message apparait dans
# la console malgre la correction ci-dessus, deux solutions : (1) idealement, exclure
# python.exe du scan HTTPS de l'antivirus (aucune perte de securite) ; (2) sinon,
# relancer avec --ignorer-verif-ssl pour ne plus verifier le certificat sur cette
# machine precise (les donnees lues sont publiques et non sensibles).
IGNORER_VERIF_SSL = "--ignorer-verif-ssl" in sys.argv
if IGNORER_VERIF_SSL:
    CONTEXTE_SSL.check_hostname = False
    CONTEXTE_SSL.verify_mode = ssl.CERT_NONE

# --- Authentification anonyme Firebase ---
# Une fois l'authentification anonyme activee dans la console Firebase (et les regles
# mises a jour pour l'exiger), ce jeton est requis pour lire/ecrire dans la base. Si
# elle n'est pas encore activee, la recuperation du jeton echoue silencieusement et le
# programme continue de fonctionner sans jeton (repli automatique, rien ne casse).
jeton_id = None
jeton_rafraichissement = None
jeton_expiration = 0


def obtenir_nouveau_jeton():
    global jeton_id, jeton_rafraichissement, jeton_expiration
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    donnees = json.dumps({"returnSecureToken": True}).encode("utf-8")
    requete = urllib.request.Request(url, data=donnees, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=5, context=CONTEXTE_SSL) as reponse:
        resultat = json.loads(reponse.read().decode("utf-8"))
    jeton_id = resultat["idToken"]
    jeton_rafraichissement = resultat["refreshToken"]
    jeton_expiration = time.time() + int(resultat["expiresIn"]) - 60


def rafraichir_jeton():
    global jeton_id, jeton_expiration
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    donnees = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": jeton_rafraichissement}).encode("utf-8")
    requete = urllib.request.Request(url, data=donnees, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(requete, timeout=5, context=CONTEXTE_SSL) as reponse:
        resultat = json.loads(reponse.read().decode("utf-8"))
    jeton_id = resultat["id_token"]
    jeton_expiration = time.time() + int(resultat["expires_in"]) - 60


def jeton_valide():
    global jeton_id
    try:
        if jeton_id is None:
            obtenir_nouveau_jeton()
        elif time.time() >= jeton_expiration:
            try:
                rafraichir_jeton()
            except Exception:
                obtenir_nouveau_jeton()
    except Exception:
        jeton_id = None  # authentification anonyme pas encore activee : on continue sans jeton
    return jeton_id


POLL_SECONDS = 1.5
SANS_BLOCAGE = "--sans-blocage" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]

if not ARGS:
    NOM_POSTE = input("Nom du poste (ex: PC 1) : ").strip()
else:
    NOM_POSTE = ARGS[0].strip()

etat = {"locked": False, "connected": False, "statut": "libre", "debut": None, "pausedMs": 0, "pauseDepuis": None, "jeu": "", "pauseRaison": None, "poste_trouve": None}
etat_lock = threading.Lock()

# --- Lancement / fermeture automatique du jeu selon l'etat du poste ---
dernier_statut_connu = "libre"
dernier_jeu_lance = None


def fermer_jeu_lance():
    global dernier_jeu_lance
    if dernier_jeu_lance:
        # Ferme par nom d'executable plutot que via la reference de lancement :
        # certains programmes passent par un petit lanceur qui se termine juste
        # apres avoir ouvert la vraie fenetre, ce qui rendrait .terminate() inutile.
        nom_exe = dernier_jeu_lance.rsplit("\\", 1)[-1]
        try:
            subprocess.run(["taskkill", "/F", "/IM", nom_exe], capture_output=True, timeout=5)
        except Exception:
            pass
    dernier_jeu_lance = None


def gerer_lancement_jeu(statut, jeu):
    global dernier_statut_connu, dernier_jeu_lance
    if statut == "encours" and dernier_statut_connu != "encours":
        chemin = JEUX_EXECUTABLES.get(jeu)
        if chemin:
            try:
                subprocess.Popen([chemin], cwd=chemin.rsplit("\\", 1)[0])
                dernier_jeu_lance = chemin
                journaliser(f"Jeu lance : {jeu} ({chemin})")
            except Exception as err:
                dernier_jeu_lance = None
                journaliser(f"Echec du lancement de {jeu} ({chemin}) : {err}")
    elif statut == "libre" and dernier_statut_connu != "libre":
        # Couvre aussi la fin normale (Terminer) et la fin groupee "Tout terminer"
        # (changement de jeu), qui passent toutes les deux par le statut "libre".
        if dernier_jeu_lance:
            journaliser(f"Fermeture du jeu en cours ({dernier_jeu_lance})")
        fermer_jeu_lance()
    dernier_statut_connu = statut


INTERVALLE_BATTEMENT = 10  # secondes


def envoyer_battement():
    # Signal de vie envoye a intervalles reguliers pour que le tableau de bord
    # (gestion-parties.html) puisse detecter qu'un PC a plante/perdu la connexion
    # (pas seulement une erreur de nom de poste, deja couverte par "poste_trouve").
    try:
        payload = json.dumps({"vu": int(time.time() * 1000)}).encode("utf-8")
        jeton = jeton_valide()
        nom_chemin = urllib.parse.quote(NOM_POSTE, safe="")
        url = (DATABASE_URL + "/festival2k27_heartbeat/" + nom_chemin + ".json"
               + ("?auth=" + jeton if jeton else ""))
        requete = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="PUT")
        urllib.request.urlopen(requete, timeout=8, context=CONTEXTE_SSL)
    except Exception:
        pass


def poll_firebase():
    base_url = DATABASE_URL + "/festival2k27_etat/postes.json"
    dernier_battement = 0
    dernier_connecte_journal = None
    dernier_poste_trouve_journal = None
    while True:
        try:
            jeton = jeton_valide()
            url = base_url + ("?auth=" + jeton if jeton else "")
            with urllib.request.urlopen(url, timeout=5, context=CONTEXTE_SSL) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))
            if isinstance(donnees, dict):
                postes = list(donnees.values())
            else:
                postes = donnees or []
            trouve = None
            for p in postes:
                if p and str(p.get("nom", "")).strip().lower() == NOM_POSTE.lower():
                    trouve = p
                    break
            nouveau_statut = (trouve or {}).get("statut", "libre")
            nouveau_jeu = (trouve or {}).get("jeu", "")
            nouvelle_raison = (trouve or {}).get("pauseRaison")
            with etat_lock:
                etat["connected"] = True
                etat["poste_trouve"] = bool(trouve)
                # "changement" verrouille meme quand le poste est redevenu "libre"
                # (le site le montre reconfigurable, mais le PC physique reste bloque).
                etat["locked"] = bool(trouve) and (nouveau_statut == "pause" or nouvelle_raison == "changement")
                etat["statut"] = nouveau_statut
                etat["debut"] = (trouve or {}).get("debut")
                etat["pausedMs"] = (trouve or {}).get("pausedMs") or 0
                etat["pauseDepuis"] = (trouve or {}).get("pauseDepuis")
                etat["pauseRaison"] = nouvelle_raison
                etat["jeu"] = nouveau_jeu
            gerer_lancement_jeu(nouveau_statut, nouveau_jeu)
            if dernier_connecte_journal is not True:
                journaliser("Connexion Firebase etablie")
                dernier_connecte_journal = True
            if bool(trouve) != dernier_poste_trouve_journal:
                if trouve:
                    journaliser(f"Poste \"{NOM_POSTE}\" trouve sur le site")
                else:
                    journaliser(f"Poste \"{NOM_POSTE}\" INTROUVABLE sur le site - verifie l'orthographe exacte")
                dernier_poste_trouve_journal = bool(trouve)
        except Exception as err:
            if dernier_connecte_journal is not False:
                journaliser(f"Connexion Firebase perdue : {err}")
                dernier_connecte_journal = False
            with etat_lock:
                etat["connected"] = False
        maintenant = time.time()
        if maintenant - dernier_battement >= INTERVALLE_BATTEMENT:
            envoyer_battement()
            dernier_battement = maintenant
        time.sleep(POLL_SECONDS)


INTERVALLE_CAPTURE = 10  # secondes


def capturer_et_envoyer_ecran():
    if not PIL_DISPONIBLE:
        return
    try:
        image = ImageGrab.grab()
        largeur_cible = 640
        ratio = largeur_cible / image.width
        image = image.resize((largeur_cible, int(image.height * ratio)))
        tampon = io.BytesIO()
        image.convert("RGB").save(tampon, format="JPEG", quality=55)
        b64 = base64.b64encode(tampon.getvalue()).decode("ascii")
        payload = json.dumps({
            "image": "data:image/jpeg;base64," + b64,
            "maj": int(time.time() * 1000),
        }).encode("utf-8")
        jeton = jeton_valide()
        nom_chemin = urllib.parse.quote(NOM_POSTE, safe="")
        url = (DATABASE_URL + "/festival2k27_captures/" + nom_chemin + ".json"
               + ("?auth=" + jeton if jeton else ""))
        requete = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="PUT")
        urllib.request.urlopen(requete, timeout=8, context=CONTEXTE_SSL)
    except Exception:
        pass


def boucle_capture_ecran():
    # Envoie un apercu de l'ecran (facon Veyon) uniquement pendant une partie active
    # ("encours") : inutile pendant une pause (l'ecran de verrou le cache de toute
    # facon) et ca evite de consommer le quota gratuit Firebase quand le poste est
    # juste au repos entre deux parties.
    while True:
        with etat_lock:
            actif = etat["statut"] == "encours"
        if actif:
            capturer_et_envoyer_ecran()
        time.sleep(INTERVALLE_CAPTURE)


def formater_duree(ms):
    secondes_totales = max(0, int(ms / 1000))
    heures, reste = divmod(secondes_totales, 3600)
    minutes, secondes = divmod(reste, 60)
    if heures > 0:
        return f"{heures:02d}:{minutes:02d}:{secondes:02d}"
    return f"{minutes:02d}:{secondes:02d}"


def elapsed_ms(snapshot):
    if snapshot["statut"] == "libre" or not snapshot["debut"]:
        return 0
    if snapshot["statut"] == "pause" and snapshot["pauseDepuis"]:
        reference = snapshot["pauseDepuis"]
    else:
        reference = int(time.time() * 1000)
    return reference - snapshot["debut"] - snapshot["pausedMs"]


# Rend le programme conscient de la mise a l'echelle Windows (125%, etc.), sinon
# Tkinter calcule des dimensions d'ecran fausses et les fenetres plein ecran /
# positionnees (chrono, verrou) finissent decalees ou hors de l'affichage reel.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- Fenetre de verrouillage (Tkinter) ---
root = tk.Tk()
root.withdraw()

overlay = tk.Toplevel(root)
overlay.configure(bg="black")
overlay.attributes("-topmost", True)
overlay.overrideredirect(True)
largeur = overlay.winfo_screenwidth()
hauteur = overlay.winfo_screenheight()
overlay.geometry(f"{largeur}x{hauteur}+0+0")

tk.Label(overlay, text="⏸", font=("Segoe UI", 100), fg="#ffb020", bg="black").pack(pady=(hauteur // 3, 20))
tk.Label(overlay, text="PAUSE", font=("Segoe UI", 48, "bold"), fg="#ffb020", bg="black").pack()
overlay_sous_titre = tk.Label(overlay, text="Annonce en cours - merci de patienter", font=("Segoe UI", 18), fg="#9494b0", bg="black")
overlay_sous_titre.pack(pady=10)

TEXTES_PAUSE = {
    "changement": "Changement de jeu en cours - merci de patienter",
}
tk.Label(overlay, text=NOM_POSTE, font=("Segoe UI", 12), fg="#9494b0", bg="black").place(x=20, y=20)
tk.Label(overlay, text="(Ctrl+Maj+Q pour quitter ce programme)", font=("Segoe UI", 10), fg="#555566", bg="black").place(x=20, y=hauteur - 40)

overlay.withdraw()
verrouille_affiche = False

# --- Petit chronometre toujours visible en haut a droite pendant la partie ---
chrono = tk.Toplevel(root)
chrono.configure(bg="black")
chrono.attributes("-topmost", True)
chrono.overrideredirect(True)
chrono_label = tk.Label(chrono, text="00:00", font=("Segoe UI", 40, "bold"), fg="#22e8ff", bg="black", padx=22, pady=10)
chrono_label.pack()
chrono.deiconify()
chrono.update()
marge = 30
chrono.geometry(f"+{largeur - chrono.winfo_width() - marge}+{marge}")
chrono.withdraw()
chrono_affiche = False


def afficher_chrono():
    global chrono_affiche
    if not chrono_affiche:
        chrono.deiconify()
        chrono.attributes("-topmost", True)
        chrono_affiche = True


def cacher_chrono():
    global chrono_affiche
    if chrono_affiche:
        chrono.withdraw()
        chrono_affiche = False


# --- Bandeau d'avertissement si le nom du poste ne correspond a rien sur le
# site : sans ca, une simple faute de frappe dans le nom (ex: "PC 1" au lieu
# de "Poste 1") faisait planer le programme en silence, sans aucun signe
# visible que quelque chose ne va pas.
avertissement = tk.Toplevel(root)
avertissement.configure(bg="#3a1400")
avertissement.attributes("-topmost", True)
avertissement.overrideredirect(True)
tk.Label(
    avertissement,
    text=f"⚠ Poste « {NOM_POSTE} » introuvable sur le site — verifie l'orthographe",
    font=("Segoe UI", 13, "bold"), fg="#ffb020", bg="#3a1400", padx=18, pady=8,
).pack()
avertissement.deiconify()
avertissement.update()
avertissement.geometry(f"+{(largeur - avertissement.winfo_width()) // 2}+16")
avertissement.withdraw()
avertissement_affiche = False


def afficher_avertissement():
    global avertissement_affiche
    if not avertissement_affiche:
        avertissement.deiconify()
        avertissement.attributes("-topmost", True)
        avertissement_affiche = True


def cacher_avertissement():
    global avertissement_affiche
    if avertissement_affiche:
        avertissement.withdraw()
        avertissement_affiche = False


def jouer_bip():
    # Joue dans un thread a part : winsound.Beep() est bloquant, et le bloquer sur
    # le thread principal figerait l'interface Tkinter pendant la duree du bip.
    def son():
        try:
            winsound.Beep(880, 160)
            time.sleep(0.02)
            winsound.Beep(1108, 160)
        except Exception:
            pass
    threading.Thread(target=son, daemon=True).start()


def afficher_verrou(raison):
    global verrouille_affiche
    if not verrouille_affiche:
        jouer_bip()
        # "changement de jeu" = la partie est terminee, le jeu est deja ferme
        # (voir gerer_lancement_jeu) : rien a suspendre dans ce cas precis.
        if raison != "changement":
            suspendre_jeu_actif()
        overlay.deiconify()
        overlay.attributes("-topmost", True)
        overlay.focus_force()
        verrouille_affiche = True


def cacher_verrou():
    global verrouille_affiche
    if verrouille_affiche:
        overlay.withdraw()
        verrouille_affiche = False
        reprendre_jeu_suspendu()


# --- Suspension du jeu actif pendant le verrou (independant du blocage clavier) ---
# Reimplemente ici ce que ferait "psutil.Process.suspend()", mais avec uniquement les
# fonctions Windows deja incluses dans Python (aucune installation supplementaire) :
# on suspend un par un tous les fils d'execution ("threads") du programme cible.
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))

TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
    ]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.Thread32First.restype = wintypes.BOOL
kernel32.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(THREADENTRY32))
kernel32.Thread32Next.restype = wintypes.BOOL
kernel32.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(THREADENTRY32))
kernel32.OpenThread.restype = wintypes.HANDLE
kernel32.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.SuspendThread.restype = wintypes.DWORD
kernel32.SuspendThread.argtypes = (wintypes.HANDLE,)
kernel32.ResumeThread.restype = wintypes.DWORD
kernel32.ResumeThread.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

PID_PROGRAMME_ACTUEL = kernel32.GetCurrentProcessId()
pid_suspendu = None


def threads_du_processus(pid):
    ids = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if not snapshot or snapshot == -1:
        return ids
    try:
        entree = THREADENTRY32()
        entree.dwSize = ctypes.sizeof(THREADENTRY32)
        trouve = kernel32.Thread32First(snapshot, ctypes.byref(entree))
        while trouve:
            if entree.th32OwnerProcessID == pid:
                ids.append(entree.th32ThreadID)
            trouve = kernel32.Thread32Next(snapshot, ctypes.byref(entree))
    finally:
        kernel32.CloseHandle(snapshot)
    return ids


def suspendre_jeu_actif():
    global pid_suspendu
    if pid_suspendu is not None:
        return
    try:
        fenetre = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fenetre, ctypes.byref(pid))
        if pid.value and pid.value != PID_PROGRAMME_ACTUEL:
            for tid in threads_du_processus(pid.value):
                poignee = kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
                if poignee:
                    kernel32.SuspendThread(poignee)
                    kernel32.CloseHandle(poignee)
            pid_suspendu = pid.value
    except Exception:
        pid_suspendu = None


def reprendre_jeu_suspendu():
    global pid_suspendu
    if pid_suspendu is not None:
        try:
            for tid in threads_du_processus(pid_suspendu):
                poignee = kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
                if poignee:
                    kernel32.ResumeThread(poignee)
                    kernel32.CloseHandle(poignee)
        except Exception:
            pass
        pid_suspendu = None


# --- Hook clavier bas niveau : bloque Alt+Tab et la touche Windows pendant le verrou ---
hook_id = None

if not SANS_BLOCAGE:
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105
    VK_TAB = 0x09
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_MENU = 0x12

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.WPARAM),
        ]

    HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    # Sur Python 64 bits, les handles/pointeurs Windows doivent etre types explicitement
    # (restype/argtypes), sinon ctypes les tronque en entier 32 bits et les appels echouent
    # silencieusement (SetWindowsHookExA renvoie alors 0 sans lever d'erreur).
    user32.SetWindowsHookExA.restype = wintypes.HHOOK
    user32.SetWindowsHookExA.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
    user32.CallNextHookEx.restype = wintypes.LPARAM
    user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)

    def bas_niveau(nCode, wParam, lParam):
        if nCode == 0:
            with etat_lock:
                verrouille = etat["locked"]
            if verrouille:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if kb.vkCode in (VK_LWIN, VK_RWIN):
                    # Le menu Demarrer s'ouvre au RELACHEMENT de la touche Windows
                    # seule (pas a l'appui) : il faut bloquer les deux evenements,
                    # sinon l'appui est bien avale mais le relachement suffit a
                    # declencher le menu quand meme.
                    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
                        return 1
                elif wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    alt_bas = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                    if kb.vkCode == VK_TAB and alt_bas:
                        return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    pointeur_hook = HOOKPROC(bas_niveau)
    hook_id = user32.SetWindowsHookExA(WH_KEYBOARD_LL, pointeur_hook, kernel32.GetModuleHandleW(None), 0)


MOT_DE_PASSE_SORTIE = "2K27"


def demander_mot_de_passe():
    resultat = {"ok": False}

    boite = tk.Toplevel(root)
    boite.title("Sortie du verrouillage")
    boite.configure(bg="#0a0a14")
    boite.attributes("-topmost", True)
    boite.resizable(False, False)
    boite.protocol("WM_DELETE_WINDOW", boite.destroy)

    tk.Label(boite, text="Mot de passe requis pour quitter", font=("Segoe UI", 12),
             fg="#e8e8f5", bg="#0a0a14").pack(padx=28, pady=(22, 10))
    champ = tk.Entry(boite, show="*", font=("Segoe UI", 14), justify="center", width=14)
    champ.pack(padx=28, pady=4)
    erreur_label = tk.Label(boite, text=" ", font=("Segoe UI", 10), fg="#ff2e88", bg="#0a0a14")
    erreur_label.pack(pady=(4, 2))

    def valider(event=None):
        if champ.get().strip() == MOT_DE_PASSE_SORTIE:
            resultat["ok"] = True
            boite.destroy()
        else:
            erreur_label.configure(text="Mot de passe incorrect")
            champ.delete(0, tk.END)

    tk.Button(boite, text="Valider", command=valider).pack(pady=(6, 20))
    champ.bind("<Return>", valider)
    boite.bind("<Escape>", lambda e: boite.destroy())

    boite.update_idletasks()
    largeur_b, hauteur_b = boite.winfo_width(), boite.winfo_height()
    x = (boite.winfo_screenwidth() - largeur_b) // 2
    y = (boite.winfo_screenheight() - hauteur_b) // 2
    boite.geometry(f"+{x}+{y}")

    champ.focus_force()
    boite.grab_set()
    boite.wait_window()
    return resultat["ok"]


def quitter(event=None):
    # Demande le mot de passe avant de fermer, pour eviter qu'un joueur quitte le
    # programme lui-meme (Ctrl+Maj+Q) pour contourner le verrouillage.
    if not demander_mot_de_passe():
        journaliser("Tentative de fermeture annulee ou refusee (mot de passe incorrect)")
        return
    journaliser("Fermeture du programme (mot de passe correct)")
    reprendre_jeu_suspendu()
    try:
        if hook_id:
            user32.UnhookWindowsHookEx(hook_id)
    except Exception:
        pass
    root.destroy()
    sys.exit(0)


root.bind_all("<Control-Shift-Q>", quitter)
overlay.bind_all("<Control-Shift-Q>", quitter)
overlay.protocol("WM_DELETE_WINDOW", quitter)


def verifier_etat():
    # Tout le corps est protege par un try/except : sans ca, une exception
    # inattendue ici (bug futur, etat Firebase mal forme...) arreterait silencieusement
    # toute la chaine root.after() - le programme resterait fige sur son dernier
    # affichage (ex: verrou reste affiche a vie) sans aucune trace visible du souci.
    # Le "finally" garantit que la boucle continue de tourner meme apres une erreur.
    try:
        with etat_lock:
            instantane = dict(etat)

        if instantane["locked"]:
            texte = TEXTES_PAUSE.get(instantane["pauseRaison"], "Annonce en cours - merci de patienter")
            overlay_sous_titre.configure(text=texte)
            afficher_verrou(instantane["pauseRaison"])
        else:
            cacher_verrou()

        if instantane["statut"] in ("encours", "pause") and instantane["pauseRaison"] != "changement":
            couleur = "#ffb020" if instantane["statut"] == "pause" else "#22e8ff"
            chrono_label.configure(text=formater_duree(elapsed_ms(instantane)), fg=couleur)
            afficher_chrono()
        else:
            cacher_chrono()

        if instantane["connected"] and instantane["poste_trouve"] is False:
            afficher_avertissement()
        else:
            cacher_avertissement()
    except Exception:
        journaliser("Erreur inattendue dans verifier_etat :\n" + traceback.format_exc())
    finally:
        root.after(500, verifier_etat)


journaliser(f"Demarrage du programme - poste \"{NOM_POSTE}\"" + (" (mode --sans-blocage)" if SANS_BLOCAGE else ""))
threading.Thread(target=poll_firebase, daemon=True).start()
threading.Thread(target=boucle_capture_ecran, daemon=True).start()
root.after(500, verifier_etat)
root.mainloop()
