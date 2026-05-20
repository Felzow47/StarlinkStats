"""Windows scheduled task for autostart at logon."""

from __future__ import annotations

import subprocess
from pathlib import Path

TASK_NAME = "StarlinkWidget"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except OSError as exc:
        return 1, str(exc)


def is_enabled() -> bool:
    code, output = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    return code == 0 and TASK_NAME.lower() in output.lower()


def enable() -> bool:
    script = _project_root() / "scripts" / "install_autostart.ps1"
    if not script.exists():
        return False
    code, _ = _run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
    )
    return code == 0


def disable() -> bool:
    script = _project_root() / "scripts" / "uninstall_autostart.ps1"
    if script.exists():
        code, _ = _run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ]
        )
        return code == 0
    code, _ = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    return code == 0
