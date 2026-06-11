"""Windows autostart registration for current user."""

from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path

from starlink_widget.core.paths import app_root, is_frozen, scripts_dir

TASK_NAME = "StarlinkWidget"


def _powershell_executable() -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidate = windir / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.is_file():
        return str(candidate)
    return "powershell"


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


def _register_script() -> Path | None:
    script = scripts_dir() / "register_autostart.ps1"
    if script.is_file():
        return script
    dev = Path(__file__).resolve().parents[2] / "scripts" / "register_autostart.ps1"
    return dev if dev.is_file() else None


def _autostart_args() -> tuple[str, str, str]:
    """(exe_path, working_dir, arguments) pour register_autostart.ps1."""
    if is_frozen():
        exe = Path(sys.executable).resolve()
        return str(exe), str(exe.parent), "--autostart"
    root = app_root()
    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    return str(pythonw), str(root), "-m starlink_widget --autostart"


def _run_key_enabled() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            winreg.QueryValueEx(key, TASK_NAME)
            return True
    except OSError:
        return False


def is_enabled() -> bool:
    code, output = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    if code == 0 and TASK_NAME.lower() in output.lower():
        return True
    return _run_key_enabled()


def enable() -> bool:
    script = _register_script()
    if script is None:
        return False
    exe, workdir, args = _autostart_args()
    code, _ = _run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ExePath",
            exe,
            "-WorkingDirectory",
            workdir,
            "-Arguments",
            args,
        ]
    )
    return code == 0


def disable() -> bool:
    uninstall = scripts_dir() / "uninstall_autostart.ps1"
    if uninstall.is_file():
        code, _ = _run(
            [
                _powershell_executable(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(uninstall),
            ]
        )
        return code == 0
    code, _ = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    return code == 0
