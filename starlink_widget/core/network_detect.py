"""Detect whether the PC is on the Starlink LAN (WiFi or Ethernet)."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.request
from datetime import date
from typing import List, Optional

from PyQt6.QtCore import QSettings

from starlink_widget.core.config import AppConfig

SETTINGS_ORG = "StarlinkWidget"
SETTINGS_APP = "Widget"
ISP_QUOTA_DAY_KEY = "isp_quota_day"
ISP_QUOTA_COUNT_KEY = "isp_quota_count"
ISP_CACHED_NAME_KEY = "isp_cached_name"

ISP_LOOKUP_DAILY_MAX = 5
_ISP_CACHE_NAME = ""
_ISP_CACHE_AT = 0.0
_ISP_CACHE_TTL_S = 3600.0


def _run(cmd: List[str], timeout: float = 5.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return (result.stdout or "") + (result.stderr or "")
    except (subprocess.TimeoutExpired, OSError):
        return ""


def get_wifi_ssid() -> Optional[str]:
    output = _run(["netsh", "wlan", "show", "interfaces"])
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("ssid") and ":" in stripped:
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                name = parts[1].strip()
                if name and name.lower() != "ssid":
                    return name
    return None


def get_default_gateway() -> Optional[str]:
    output = _run(["route", "print", "-4"])
    for line in output.splitlines():
        if "0.0.0.0" in line and "On-link" not in line:
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "0.0.0.0":
                gateway = parts[2]
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", gateway):
                    return gateway
    return None


def can_reach_dish(
    host: str = "192.168.100.1",
    port: int = 9200,
    *,
    timeout_ms: int = 350,
) -> bool:
    """Teste si le port gRPC Starlink est joignable."""
    timeout_s = max(0.05, timeout_ms / 1000)
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def clear_isp_cache() -> None:
    """Vide le cache mémoire (pas le quota journalier ni le nom persisté)."""
    global _ISP_CACHE_NAME, _ISP_CACHE_AT
    _ISP_CACHE_NAME = ""
    _ISP_CACHE_AT = 0.0


def _isp_settings() -> QSettings:
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def _today_key() -> str:
    return date.today().isoformat()


def _load_persisted_isp_name() -> str:
    return str(_isp_settings().value(ISP_CACHED_NAME_KEY) or "").strip()


def _isp_quota_count(for_day: str) -> int:
    settings = _isp_settings()
    stored_day = str(settings.value(ISP_QUOTA_DAY_KEY) or "")
    if stored_day != for_day:
        return 0
    try:
        return max(0, int(settings.value(ISP_QUOTA_COUNT_KEY) or 0))
    except (TypeError, ValueError):
        return 0


def _isp_quota_remaining(*, daily_max: int = ISP_LOOKUP_DAILY_MAX) -> int:
    limit = max(0, daily_max)
    return max(0, limit - _isp_quota_count(_today_key()))


def _record_isp_lookup(name: str) -> None:
    settings = _isp_settings()
    today = _today_key()
    count = _isp_quota_count(today) + 1
    settings.setValue(ISP_QUOTA_DAY_KEY, today)
    settings.setValue(ISP_QUOTA_COUNT_KEY, count)
    settings.setValue(ISP_CACHED_NAME_KEY, name)
    settings.sync()


def get_isp_name(
    *,
    force_refresh: bool = False,
    daily_max: int = ISP_LOOKUP_DAILY_MAX,
) -> Optional[str]:
    """Nom du FAI via ip-api.com, plafonné à daily_max requêtes HTTP / jour."""
    global _ISP_CACHE_NAME, _ISP_CACHE_AT
    now = time.monotonic()
    persisted = _load_persisted_isp_name()
    if (
        not force_refresh
        and _ISP_CACHE_NAME
        and now - _ISP_CACHE_AT < _ISP_CACHE_TTL_S
    ):
        return _ISP_CACHE_NAME
    if not force_refresh and persisted and _isp_quota_remaining(daily_max=daily_max) <= 0:
        _ISP_CACHE_NAME = persisted
        _ISP_CACHE_AT = now
        return persisted
    if _isp_quota_remaining(daily_max=daily_max) <= 0:
        return persisted or None
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/?fields=status,isp,org",
            headers={"User-Agent": "StarlinkWidget/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            name = (data.get("isp") or data.get("org") or "").strip()
            if name:
                _record_isp_lookup(name)
                _ISP_CACHE_NAME = name
                _ISP_CACHE_AT = now
                return name
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    if persisted:
        _ISP_CACHE_NAME = persisted
        _ISP_CACHE_AT = now
        return persisted
    return _ISP_CACHE_NAME or None


def get_connection_profile_name() -> Optional[str]:
    """Nom du profil réseau Windows (Ethernet ou Wi‑Fi)."""
    output = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-NetConnectionProfile | Where-Object { "
            "$_.IPv4Connectivity -ne 'NoTraffic' -and "
            "$_.IPv4Connectivity -ne 'Disconnected' } | "
            "Select-Object -First 1 -ExpandProperty Name)",
        ],
        timeout=4.0,
    )
    name = output.strip()
    if not name:
        return None
    if name.lower() in (
        "network",
        "identifying...",
        "unidentified network",
        "réseau",
        "reseau",
    ):
        return None
    return name


def get_off_network_label(*, daily_max: int = ISP_LOOKUP_DAILY_MAX) -> str:
    """Libellé du réseau actuel quand on n'est pas sur Starlink."""
    isp = get_isp_name(daily_max=daily_max)
    if isp:
        return isp
    ssid = get_wifi_ssid()
    if ssid:
        return ssid
    profile = get_connection_profile_name()
    if profile:
        return profile
    gateway = get_default_gateway()
    if gateway:
        return f"passerelle {gateway}"
    return "autre réseau"


def is_on_starlink_lan(config: AppConfig) -> bool:
    """Vrai si le protocole/port dédié de la dish répond."""
    host = config.starlink_host
    port = config.starlink_port
    return can_reach_dish(host, port)


def active_network_signature() -> str:
    """Empreinte du réseau actif (SSID/profil/passerelle)."""
    ssid = get_wifi_ssid() or ""
    profile = get_connection_profile_name() or ""
    gateway = get_default_gateway() or ""
    parts = [
        f"wifi:{ssid.lower()}",
        f"profile:{profile.lower()}",
        f"gw:{gateway}",
    ]
    return "|".join(parts)


class StarlinkPresenceTracker:
    """Évite les faux "hors réseau" pendant un reboot de la dish."""

    def __init__(
        self,
        *,
        hide_after_ticks: int = 1,
        reboot_grace_ticks: int = 45,
    ) -> None:
        self._visibility = NetworkPresenceTracker(hide_after_ticks=hide_after_ticks)
        self.reboot_grace_ticks = max(0, reboot_grace_ticks)
        self._grace_left = 0
        self._last_starlink_signature = ""

    def update(self, protocol_reachable: bool) -> tuple[bool, bool]:
        signature = active_network_signature()
        if protocol_reachable:
            if signature:
                self._last_starlink_signature = signature
            self._grace_left = self.reboot_grace_ticks
            on_starlink_lan = True
        else:
            same_network = (
                bool(signature)
                and bool(self._last_starlink_signature)
                and signature == self._last_starlink_signature
            )
            unknown_network = not bool(signature)
            if self._grace_left > 0 and (same_network or unknown_network):
                self._grace_left -= 1
                on_starlink_lan = True
            else:
                self._grace_left = 0
                on_starlink_lan = False
                if signature and signature != self._last_starlink_signature:
                    self._last_starlink_signature = ""
        visible = self._visibility.update(on_starlink_lan)
        return on_starlink_lan, visible


class NetworkPresenceTracker:
    """Hystérésis : masquer hors Starlink, afficher dès le retour."""

    def __init__(self, hide_after_ticks: int = 1) -> None:
        self.hide_after_ticks = max(1, hide_after_ticks)
        self._off_count = 0
        self._visible = False

    def update(self, on_lan: bool) -> bool:
        """Indique si le widget doit être visible."""
        if on_lan:
            self._off_count = 0
            self._visible = True
        else:
            self._off_count += 1
            if self._off_count >= self.hide_after_ticks:
                self._visible = False
        return self._visible
