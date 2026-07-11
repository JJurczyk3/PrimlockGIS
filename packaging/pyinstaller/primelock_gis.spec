# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parents[1]
source_root = project_root / "src"

polars_datas, polars_binaries, polars_hiddenimports = collect_all(
    "polars",
    include_py_files=False,
    filter_submodules=lambda name: not name.startswith("polars.testing"),
)
polars_datas = [
    item
    for item in polars_datas
    if not item[0].endswith(".pyi") and not item[0].endswith("py.typed")
]

a = Analysis(
    [str(source_root / "primelock_gis" / "__main__.py")],
    pathex=[str(source_root)],
    binaries=polars_binaries,
    datas=[
        (str(project_root / "data" / "initial_coords.csv"), "data"),
        *polars_datas,
    ],
    hiddenimports=polars_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyInstaller",
        "hypothesis",
        "pip",
        "polars.testing",
        "setuptools",
    ],
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
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_root / "packaging" / "pyinstaller" / "version_info.txt"),
    icon=str(project_root / "packaging" / "icons" / "PrimelockGIS.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PrimelockGIS",
)
