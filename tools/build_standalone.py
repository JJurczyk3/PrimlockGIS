"""Build a standalone Primelock GIS application folder for the current OS."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "packaging" / "pyinstaller" / "primelock_gis.spec"
DIST_APP_DIR = PROJECT_ROOT / "dist" / "PrimelockGIS"
RELEASE_DIR = PROJECT_ROOT / "release"


def main() -> None:
    os_name = platform.system()
    label = platform_label(os_name)

    run_pyinstaller()
    assemble_release_folder(label)

    print(f"Built release/{label}")


def platform_label(os_name: str) -> str:
    if os_name == "Windows":
        return "Windows"
    if os_name == "Darwin":
        return "macOS"
    if os_name == "Linux":
        return "Linux"

    raise SystemExit(f"Unsupported build platform: {os_name}")


def run_pyinstaller() -> None:
    if not SPEC_PATH.exists():
        raise SystemExit(f"Missing PyInstaller spec: {SPEC_PATH}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC_PATH),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def assemble_release_folder(label: str) -> None:
    if not DIST_APP_DIR.exists():
        raise SystemExit(f"Missing PyInstaller output: {DIST_APP_DIR}")

    output_dir = RELEASE_DIR / label
    if output_dir.exists():
        shutil.rmtree(output_dir)

    shutil.copytree(DIST_APP_DIR, output_dir)
    shutil.copytree(PROJECT_ROOT / "data", output_dir / "data")
    copy_launchers(label, output_dir)


def copy_launchers(label: str, output_dir: Path) -> None:
    if label == "Windows":
        template_dir = PROJECT_ROOT / "packaging" / "runtime" / "windows"
    else:
        template_dir = PROJECT_ROOT / "packaging" / "runtime" / "posix"

    for launcher in template_dir.iterdir():
        target = output_dir / launcher.name
        shutil.copy2(launcher, target)
        if target.suffix == ".sh":
            target.chmod(target.stat().st_mode | 0o755)


if __name__ == "__main__":
    main()
