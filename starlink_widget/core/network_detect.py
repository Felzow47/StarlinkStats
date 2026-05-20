"""Detect whether the PC is on the Starlink LAN (WiFi or Ethernet)."""

from __future__ import annotations

import re
import subprocess
from typing import List, Optional

from starlink_widget.core.config import AppConfig


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


def is_on_starlink_lan(config: AppConfig) -> bool:
    """Return True if at least one configured Starlink LAN signal matches."""
    results: List[bool] = []

    if config.starlink_gateway_prefixes:
        gateway = get_default_gateway()
        results.append(
            gateway is not None
            and any(gateway.startswith(p) for p in config.starlink_gateway_prefixes)
        )

    if config.starlink_wifi_ssids:
        ssid = get_wifi_ssid()
        if ssid:
            results.append(ssid in config.starlink_wifi_ssids)

    if config.starlink_require_dish_route:
        results.append(has_route_to_dish(config.starlink_host))

    return any(results) if results else False


class NetworkPresenceTracker:
    """Hysteresis: hide after N off ticks, show immediately on return."""

    def __init__(self, hide_after_ticks: int = 3) -> None:
        self.hide_after_ticks = hide_after_ticks
        self._off_count = 0
        self._visible = True

    def update(self, on_lan: bool) -> bool:
        """Return whether the widget should be visible."""
        if on_lan:
            self._off_count = 0
            self._visible = True
        else:
            self._off_count += 1
            if self._off_count >= self.hide_after_ticks:
                self._visible = False
        return self._visible
