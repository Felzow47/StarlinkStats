# Starlink Always-on-Top Widget

[Version française](README.md)

Small Windows desktop widget (Python + PyQt6) that displays your Starlink dish status in real time via local gRPC (`192.168.100.1:9200`).

Personal project, work in progress - not an official SpaceX/Starlink product.

> [!CAUTION]
> **Disclaimer - AI usage**
>
> A significant part of the code (~50%) was written **with the help of AI tools**. I would have preferred not to use AI, but on this project I got stuck on several points and ended up using it anyway.
>
> The result is still a homemade tool: it may contain bugs, regressions, or debatable choices. **Feedback, issues, and PRs are welcome** - especially if you prefer fixing things by hand rather than via a prompt.

## Features

### Display & status

- Compact window, dark mode, **always on top**
- Polling every second (dish gRPC + Internet ping to `1.1.1.1` by default)
- Color codes: **green** (OK), **orange** (no Internet / alerts), **red + flash** (dish unreachable)
- Metrics: up/down throughput (sparklines), ping latency / loss, Gen 3 azimuth delta, software version, alerts (obstruction, thermal, ethernet...)
- **Ping-loss obstruction**: enter if loss > 60%, exit if loss < 30% (hysteresis), in addition to the Starlink gRPC flag


**Language: French only (UI).** The widget interface (window, menus, alerts, Customize dialog) is entirely in French. There is **no translation system** (no i18n, no `.po`/locale JSON files): labels are **hardcoded** in the source (`display_fields.py`, `state.py`, `ui/`, etc.). No other UI language is planned for now.

### Passive mode

When not customizing, the widget is **click-through**: it does not block clicks underneath. On hover it fades out; it reappears when the mouse moves away.

### Starlink network

- **Auto-hide** when the dish is no longer reachable (other Wi-Fi, ISP, mobile hotspot...)
- Primary detection: **TCP connection or ping to `192.168.100.1`** - works over **Ethernet** and Wi-Fi (SSID name does not matter)
- Optional Starlink Wi-Fi SSID and dish route fallback (`config.json`)
- System tray icon: shows **current ISP / network name** when off Starlink (ISP via ip-api.com, **5 requests/day max**; otherwise SSID or Windows profile)

### Customization

- **Customize...** menu (tray icon)
- Show/hide fields, reorder via drag-and-drop in the list
- **2-column grid**: resizable cards (bottom-right handle), drag to move cards
- Preferences persisted (Windows registry `HKCU\Software\StarlinkWidget`)

### Startup

- **Logon autostart** via Task Scheduler (30 s delay), toggle from the tray menu

---

## Requirements

- Windows 10/11
- Python 3.10+
- Local network access to the Starlink dish (`192.168.100.1`)

## Installation

For testing, use `launch_widget.bat` in the `scripts` folder:

```
.\scripts\launch_widget.bat
```

---

## `config.json`

```json
{
  "starlink_host": "192.168.100.1",
  "starlink_port": 9200,
  "ping_target": "1.1.1.1",
  "poll_interval_ms": 1000,
  "starlink_gateway_prefixes": ["192.168.1."],
  "starlink_wifi_ssids": [],
  "starlink_require_dish_route": true,
  "hide_after_ticks_off_network": 1,
  "isp_lookup_daily_max": 5
}
```

| Key | Purpose |
|-----|---------|
| `starlink_host` / `starlink_port` | Dish gRPC address |
| `ping_target` | Internet ping target (ICMP) |
| `poll_interval_ms` | Polling interval |
| `starlink_wifi_ssids` | Optional Starlink SSID(s) (often empty on Ethernet) |
| `starlink_require_dish_route` | Also check for a route to `192.168.100.x` |
| `hide_after_ticks_off_network` | Poll cycles before hiding off Starlink (1 ≈ 1 s) |
| `isp_lookup_daily_max` | Max ip-api.com requests/day for ISP name (default: 5) |

**Network detection:** by default the widget checks whether the dish responds (port 9200 or ping). SSID is only used if you list names in `starlink_wifi_ssids`.

---

## Launch

```powershell
.\scripts\launch_widget.bat
```

Tray menu: **Start with Windows** (check / uncheck).

> `launch_widget.bat` stops running instances, clears caches, **resets preferences** (registry + AppData), then starts the widget. Fine for dev; avoid it if you want to keep your custom layout.

---

## Test checklist

1. Dish OK + Internet → **green** background, throughput shown
2. Cut WAN / satellite (dish still reachable) → **orange** "SANS INTERNET"
3. Cut dish power → **red + flash**
4. Obstruction or high ping loss → alert visible
5. Stable CPU/RAM after 1 h
6. PC reboot → widget after ~30 s (if autostart installed)
7. Hotspot / other ISP → widget **hidden**, tray shows current network
8. Back on Starlink → widget **reappears**
9. Customize → order / fields / sizes → persist after restart (without `launch_widget.bat`)

---

## Project structure

```
starlink-widget/
  starlink_widget/
    core/           # gRPC, network, health state, card/field prefs, autostart
    ui/             # window, grid, metric tiles, Customize dialog
    workers/        # polling thread
    vendor/         # starlink_grpc (sparky8512)
  scripts/
    launch_widget.bat
    clean_widget.ps1
    install_autostart.ps1
    uninstall_autostart.ps1
  config.json.example
  requirements.txt
```

---

## Help & contributions

- **Bug or idea?** Open an issue with OS, network mode (Ethernet / Wi-Fi), expected vs actual behavior.
- **PRs:** focused fixes appreciated; please explain the "why" in the commit message.
- Drag & drop and move cards is still rough - real-world feedback helps.

---

## License & credits

Thanks to sparky8512 for starlink-grpc-tools.

- `vendor/starlink_grpc.py`: [starlink-grpc-tools](https://github.com/sparky8512/starlink-grpc-tools) (MIT)
- Off-Starlink ISP detection: [ip-api.com](http://ip-api.com) (HTTP, capped at 5 req/day by default; beyond that: SSID / Windows profile)
