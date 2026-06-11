"""Internet connectivity check via ICMP ping."""

from __future__ import annotations

import subprocess
from typing import Optional


_PING_FAILURE_MARKERS = (
    "impossible de joindre",
    "destination host unreachable",
    "impossible de joindre l'hote de destination",
    "impossible de joindre l’hote de destination",
    "impossible de joindre l'hôte de destination",
    "request timed out",
    "delai d'attente de la demande depasse",
    "délai d'attente de la demande dépassé",
    "general failure",
)

_PING_SUCCESS_MARKERS = (
    "ttl=",
    " time=",
    " temps=",
)


def ping_host(host: str, timeout_ms: int = 800) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), host],
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=(timeout_ms / 1000) + 2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = ((result.stdout or "") + (result.stderr or "")).lower()
        if any(marker in output for marker in _PING_FAILURE_MARKERS):
            return False
        if any(marker in output for marker in _PING_SUCCESS_MARKERS):
            return True
        return False
    except (subprocess.TimeoutExpired, OSError):
        return False


def check_internet(target: Optional[str] = None, config_target: str = "1.1.1.1") -> bool:
    return ping_host(target or config_target)
