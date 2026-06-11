# Widget Starlink Always-on-Top

<p align="center">
  <img src="assets/Vector.svg" alt="Starlink Widget" width="128">
</p>

[English version](README.en.md)

Petit widget de bureau Windows (Python + PyQt6) qui affiche en temps réel l'état de votre antenne Starlink via gRPC local (`192.168.100.1:9200`).

Projet perso, en évolution - pas un produit officiel SpaceX/Starlink.

> [!CAUTION]
> **Disclaimer - usage d'IA**
>
> Une bonne partie du code (~50 %) a été écrite **avec l'aide d'outils d'IA**. j'aurais préféré ne pas utiliser d'IA, mais sur ce projet j'étais bloqué sur plusieurs points et j'ai fini par m'en servir quand même.
>
> Le résultat reste un outil maison : il peut contenir des bugs, des régressions, ou des choix discutables. **Les retours, issues et PR sont les bienvenus** - surtout si vous préférez corriger à la main plutôt que via un prompt.

## Fonctionnalités

### Affichage & état

- Fenêtre compacte, dark mode, **always on top**
- Polling chaque seconde (gRPC dish + ping Internet vers `1.1.1.1` par défaut)
- Code couleur : **vert** (OK), **orange** (sans Internet / alertes), **rouge + flash** (antenne injoignable)
- Métriques : débits up/down (sparklines), latence / perte ping, écart azimut Gen 3, version logiciel, alertes (obstruction, thermique, ethernet...)
- **Obstruction déduite de la perte ping** : entrée si perte > 60 %, sortie si perte < 30 % (hystérésis), en plus du flag gRPC Starlink

### Mode passif

Hors mode personnalisation, le widget est **click-through** : il ne gêne pas les clics sous la fenêtre. Au survol, il disparaît en fondu ; il réapparaît quand la souris s'éloigne.

### Réseau Starlink

- **Masquage automatique** quand la dish n'est plus joignable (autre Wi-Fi, autre FAI, 4G...)
- Détection principale : **connexion TCP ou ping vers `192.168.100.1`** - fonctionne en **Ethernet** comme en Wi-Fi (le nom du SSID n'a pas d'importance)
- SSID Wi-Fi Starlink et route vers la dish en secours optionnels (`config.json`)
- Icône barre des tâches : affiche le **nom du FAI / réseau actuel** quand vous n'êtes pas sur Starlink (FAI via ip-api.com, **5 requêtes / jour max** ; sinon SSID ou profil Windows)

### Personnalisation

- Menu **Personnaliser...** (icône barre des tâches )
- Champs affichables / masquables, ordre par glisser-déposer dans la liste
- Grille **2 colonnes** : cartes redimensionnables (coin bas-droit), déplacement par drag des cartes
- Préférences persistées (registre Windows `HKCU\Software\StarlinkWidget`)

**Langue : français uniquement.** L'interface (widget, menus, alertes, dialogue Personnaliser) est entièrement en français. Il n'y a **aucun système de traduction** (pas de i18n, pas de fichiers `.po`/`.json` de locales) : les libellés sont **codés en dur** dans le code (`display_fields.py`, `state.py`, `ui/`, etc.). Aucune autre langue n'est prévue pour le moment.

### Démarrage

- **Démarrage au logon** via Planificateur de tâches (délai 30 s), activable depuis le menu tray

---

## Prérequis

- Windows 10/11
- Python 3.10+
- Accès réseau local à l'antenne Starlink (`192.168.100.1`)

## Installation

### Installeur Windows (recommande)

1. Compiler (installeur **NSIS** ; telecharge automatiquement au premier build, sans Inno Setup) :

```powershell
.\scripts\build_installer.ps1
```

2. Distribuer `dist\installer\StarlinkWidget-Setup.exe`

L'assistant d'installation propose :
- **Lancer au demarrage de Windows** (tache planifiee, delai 30 s)
- Raccourci Bureau (optionnel)

Installation par defaut : `%LOCALAPPDATA%\StarlinkWidget`

**Icone** : `assets\Vector.svg` (source) / `assets\starlink_widget.ico` (genere automatiquement au build).

### Developpement / tests

```powershell
.\scripts\launch_widget.bat
```

---

## Configuration `config.json`

```json
{
  "starlink_host": "192.168.100.1",
  "starlink_port": 9200,
  "ping_target": "1.1.1.1",
  "poll_interval_ms": 1000,
  "hide_after_ticks_off_network": 1,
  "dish_reboot_grace_ticks": 45,
  "isp_lookup_daily_max": 5
}
```

| Clé | Rôle |
|-----|------|
| `starlink_host` / `starlink_port` | Adresse gRPC de la dish |
| `ping_target` | Cible du test Internet (ICMP) |
| `poll_interval_ms` | Intervalle de polling |
| `hide_after_ticks_off_network` | Nombre de cycles avant masquage hors Starlink (1 ≈ 1 s) |
| `dish_reboot_grace_ticks` | Tolérance (cycles) pendant un reboot dish avant de passer hors Starlink |
| `isp_lookup_daily_max` | Requêtes max / jour vers ip-api.com pour le nom du FAI (défaut : 5) |

**Détection réseau** : le widget considère Starlink actif uniquement si le port dish `9200` répond. En cas de reboot dish, `dish_reboot_grace_ticks` évite un basculement immédiat vers « Hors réseau Starlink ».

---

## Lancement

```powershell
.\scripts\launch_widget.bat
```

Menu tray : **Démarrer avec Windows** (coche / décoche).

> `launch_widget.bat` arrête les instances en cours, nettoie les caches, **réinitialise les préférences** (registre + AppData), puis relance le widget. Utile en dev ; à éviter si vous voulez garder votre layout personnalisé.

---

## Checklist de tests

1. Antenne OK + Internet → fond **vert**, débits affichés
2. Couper WAN / satellite (antenne joignable) → **orange** « SANS INTERNET »
3. Couper alimentation antenne → **rouge + flash**
4. Obstruction ou forte perte ping → alerte visible
5. CPU / RAM stables après 1 h
6. Redémarrage PC → widget après ~30 s (si autostart installé)
7. Hotspot / autre FAI → widget **masqué**, tray indique le réseau actuel
8. Retour sur Starlink → widget **réapparaît**
9. Personnaliser → ordre / champs / tailles → persistance après redémarrage (sans `launch_widget.bat`)

---

## Structure du projet

```
starlink-widget/
  starlink_widget/
    core/           # gRPC, réseau, état santé, prefs cartes/champs, autostart
    ui/             # fenêtre, grille, cartes métriques, dialogue Personnaliser
    workers/        # thread de polling
    vendor/         # starlink_grpc (sparky8512)
  scripts/
    build_installer.ps1    # PyInstaller + NSIS
    launch_widget.bat      # lancement + reset prefs (dev)
    clean_widget.ps1       # nettoyage appelé par launch_widget.bat
    register_autostart.ps1   # tache planifiee (installeur + tray)
    install_autostart.ps1    # variante dev (pythonw)
    uninstall_autostart.ps1
    uninstall_cleanup.ps1   # desinstallation complete (registre, tache, AppData)
  installer/
    starlink_widget.spec
    starlink_widget.nsi
  assets/
    README.txt
  config.json.example
  requirements.txt
```

---

## Aide & contributions

- **Bug ou idée ?** Ouvrez une issue avec OS, mode réseau (Ethernet / Wi-Fi), et ce que vous attendiez vs ce que vous voyez.
- **PR** : corrections ciblées appréciées ; merci de décrire le « pourquoi » dans le message de commit.
- Le layout drag & drop et deplacement des cartes est une zone encore perfectible - les retours d'usage concrets aident.

---

## Licence & crédits

Merci à sparky8512 pour son outil starlink-grpc-tools.

- `vendor/starlink_grpc.py` : [starlink-grpc-tools](https://github.com/sparky8512/starlink-grpc-tools) (MIT)
- Détection FAI hors Starlink : [ip-api.com](http://ip-api.com) (HTTP, plafonné à 5 req/jour par défaut ; au-delà : SSID / profil Windows)
