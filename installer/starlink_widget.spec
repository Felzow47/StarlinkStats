# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec - lance depuis la racine du projet."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
ICON = ROOT / "assets" / "starlink_widget.ico"

datas = [
    (str(ROOT / "config.json.example"), "."),
    (str(ROOT / "assets" / "starlink_widget.ico"), "assets"),
]
binaries = []
hiddenimports = ["starlink_widget.vendor.starlink_grpc"]

for pkg in ("grpc", "google.protobuf"):
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hiddenimports += tmp[2]
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "starlink_widget" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["starlink_widget.vendor.starlink_grpc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StarlinkWidget",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StarlinkWidget",
)
