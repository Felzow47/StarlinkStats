"""Windows autostart registration for current user."""

from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path

from starlink_widget.core.paths import app_root, is_frozen, scripts_dir

TASK_NAME = "StarlinkWidget"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APPROVED_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
)
# 0x02 = enabled. Windows treats the low bit as "disabled" (0x03 / 0x07).
_APPROVED_ENABLED = bytes([0x02]) + bytes(11)


def _pythonw() -> Path | None:
    candidates = [
        app_root() / ".venv" / "Scripts" / "pythonw.exe",
        Path(sys.executable).with_name("pythonw.exe"),
        Path(sys.executable),
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def _command() -> str | None:
    """Commande HKCU\\...\\Run : exe réel, pas wscript (souvent désactivé par Windows)."""
    if is_frozen():
        exe = Path(sys.executable).resolve()
        if not exe.is_file():
            return None
        return f'"{exe}" --autostart'

    pythonw = _pythonw()
    if pythonw is None:
        return None
    entry = scripts_dir() / "autostart_entry.py"
    if entry.is_file():
        return f'"{pythonw}" "{entry.resolve()}"'
    root = app_root()
    return f'cmd.exe /c cd /d "{root}" && start "" "{pythonw}" -m starlink_widget --autostart'


def _delete_value(key_path: str, name: str) -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def _run_key_command() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _regtype = winreg.QueryValueEx(key, TASK_NAME)
    except OSError:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _startup_approved_disabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_KEY) as key:
            value, _regtype = winreg.QueryValueEx(key, TASK_NAME)
    except OSError:
        return False
    if not value:
        return False
    data = bytes(value)
    return bool(data) and (data[0] & 1) == 1


def _set_startup_approved(enabled: bool) -> None:
    payload = _APPROVED_ENABLED if enabled else bytes([0x03]) + bytes(11)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_KEY) as key:
        winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_BINARY, payload)


def _remove_legacy_scheduled_task() -> None:
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        pass


def is_enabled() -> bool:
    """Vrai seulement si Windows lancera réellement l'entrée au logon."""
    return _run_key_command() is not None and not _startup_approved_disabled()


def enable() -> bool:
    command = _command()
    if command is None:
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_SZ, command)
        _set_startup_approved(True)
    except OSError:
        return False
    _remove_legacy_scheduled_task()
    return is_enabled()


def disable() -> bool:
    _delete_value(RUN_KEY, TASK_NAME)
    _delete_value(STARTUP_APPROVED_KEY, TASK_NAME)
    _remove_legacy_scheduled_task()
    return not is_enabled()
