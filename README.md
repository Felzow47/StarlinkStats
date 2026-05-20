# Widget Starlink Always-on-Top

Widget de bureau Windows (Python + PyQt6) affichant en temps réel l'état de votre antenne Starlink via gRPC local (`192.168.100.1:9200`).

## Fonctionnalités

- Fenêtre compacte, dark mode, **always on top**
- Polling chaque seconde (gRPC + ping Internet `1.1.1.1`)
- Code couleur : **vert** (OK), **orange** (sans Internet / alertes), **rouge + flash** (antenne injoignable)
- Alignement Gen 3 (delta azimut), débits up/down, alertes obstruction / thermique / ethernet
- **Masquage automatique** hors réseau Starlink (autre WiFi ou Ethernet)
- **Démarrage au logon** via Planificateur de tâches (délai 30 s)

## Prérequis

- Windows 10/11
- Python 3.10+
- Accès réseau local à l'antenne Starlink (`192.168.100.1`)
- Route statique ou mode « own router » si nécessaire (voir doc Starlink)
- Option « Allow access on local network » dans l'app Starlink

### Vérifier gRPC (une fois)

```powershell
# Si grpcurl est installé :
grpcurl -plaintext -d "{\"get_status\":{}}" 192.168.100.1:9200 SpaceX.API.Device.Device/Handle
```

## Installation

```powershell
cd C:\Users\Felzow47\Projects\starlink-widget
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy config.json.example config.json
```

### Configuration `config.json`

```json
{
  "starlink_host": "192.168.100.1",
  "starlink_port": 9200,
  "ping_target": "1.1.1.1",
  "poll_interval_ms": 1000,
  "starlink_gateway_prefixes": ["192.168.1."],
  "starlink_wifi_ssids": ["NomDeVotreWiFiStarlink"],
  "starlink_require_dish_route": true,
  "hide_after_ticks_off_network": 3
}
```

Trouver votre SSID WiFi Starlink :

```powershell
netsh wlan show interfaces
```

Si vous êtes en **Ethernet uniquement** derrière le routeur Starlink, laissez `starlink_wifi_ssids` vide — la détection utilise la passerelle `192.168.1.x`.

## Lancement

```powershell
.\.venv\Scripts\pythonw.exe -m starlink_widget
```

Ou double-clic sur `scripts\launch_widget.bat` (après installation venv).

## Démarrage automatique

```powershell
.\scripts\install_autostart.ps1
```

Crée la tâche `StarlinkWidget` (logon + 30 s de délai).

Désinstallation :

```powershell
.\scripts\uninstall_autostart.ps1
```

Menu tray : **Démarrer avec Windows** (coche/décoche).

## Checklist de tests

1. Antenne OK + Internet → fond **vert**, débits affichés
2. Couper WAN/satellite (antenne joignable) → **orange** « SANS INTERNET »
3. Couper alimentation antenne → **rouge + flash**
4. Obstruction → alerte visible
5. CPU/RAM stables après 1 h
6. Redémarrage PC → widget après ~30 s (si autostart installé)
7. Hotspot / autre WiFi → widget **masqué** en ~3 s
8. Retour réseau Starlink → widget **réapparaît**

## Structure

```
starlink-widget/
  starlink_widget/
    core/          # gRPC, réseau, état, autostart
    ui/            # fenêtre PyQt6
    workers/       # polling thread
    vendor/        # starlink_grpc (sparky8512)
  scripts/         # lancement et autostart
  config.json
```

## Licence

Le module `vendor/starlink_grpc.py` provient de [starlink-grpc-tools](https://github.com/sparky8512/starlink-grpc-tools) (MIT).
