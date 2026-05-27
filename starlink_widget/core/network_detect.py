"""Detect whether the PC is on the Starlink LAN (WiFi or Ethernet)."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.request
from typing import List, Optional

from starlink_widget.core.config import AppConfig
from starlink_widget.core.connectivity import ping_host

_ISP_CACHE_NAME = ""
_ISP_CACHE_AT = 0.0
_ISP_CACHE_TTL_S = 60.0


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


def has_route_to_dish(host: str = "192.168.100.1") -> bool:
    output = _run(["route", "print", "-4"])
    prefix = ".".join(host.split(".")[:3])
    for line in output.splitlines():
        if prefix in line or host in line:
            if "192.168.100" in line:
                return True
    return False


def can_reach_dish(
    host: str = "192.168.100.1",
    port: int = 9200,
    *,
    timeout_ms: int = 350,
) -> bool:
    """Teste si la dish Starlink répond (Ethernet ou WiFi, SSID indifférent)."""
    timeout_s = max(0.05, timeout_ms / 1000)
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        pass
    return ping_host(host, timeout_ms=timeout_ms)


def clear_isp_cache() -> None:
    global _ISP_CACHE_NAME, _ISP_CACHE_AT
    _ISP_CACHE_NAME = ""
    _ISP_CACHE_AT = 0.0


def get_isp_name(*, force_refresh: bool = False) -> Optional[str]:
    """Nom du FAI via l'IP publique (ex. Free, Orange, Starlink)."""
    global _ISP_CACHE_NAME, _ISP_CACHE_AT
    now = time.monotonic()
    if (
        not force_refresh
        and _ISP_CACHE_NAME
        and now - _ISP_CACHE_AT < _ISP_CACHE_TTL_S
    ):
        return _ISP_CACHE_NAME
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
                _ISP_CACHE_NAME = name
                _ISP_CACHE_AT = now
                return name
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
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


def get_off_network_label() -> str:
    """Libellé du réseau actuel quand on n'est pas sur Starlink."""
    isp = get_isp_name()
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
    """Vrai si la dish Starlink est joignable sur le LAN local."""
    host = config.starlink_host
    port = config.starlink_port

    if can_reach_dish(host, port):
        return True

    if config.starlink_wifi_ssids:
        ssid = get_wifi_ssid()
        if ssid and ssid in config.starlink_wifi_ssids:
            return True

    if config.starlink_require_dish_route and has_route_to_dish(host):
        return True

    return False


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
