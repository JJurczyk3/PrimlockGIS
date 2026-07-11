# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parents[1]
source_root = project_root / "src"

polars_datas, polars_binaries, polars_hiddenimports = collect_all("polars")

a = Analysis(
    [str(source_root / "primelock_gis" / "__main__.py")],
    pathex=[str(source_root)],
    binaries=polars_binaries,
    datas=[
        (str(project_root / "data"), "data"),
        *polars_datas,
    ],
    hiddenimports=polars_hiddenimports,
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
    name="PrimelockGIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PrimelockGIS",
)
