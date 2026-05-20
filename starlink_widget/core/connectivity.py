"""Internet connectivity check via ICMP ping."""

from __future__ import annotations

import subprocess
from typing import Optional


def ping_host(host: str, timeout_ms: int = 800) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), host],
            capture_output=True,
            timeout=(timeout_ms / 1000) + 2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def check_internet(target: Optional[str] = None, config_target: str = "1.1.1.1") -> bool:
    return ping_host(target or config_target)
