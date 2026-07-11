"""Build a standalone Primelock GIS application folder for the current OS."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "packaging" / "pyinstaller" / "primelock_gis.spec"
DIST_APP_DIR = PROJECT_ROOT / "dist" / "PrimelockGIS"
RELEASE_DIR = PROJECT_ROOT / "release"


def main() -> None:
    os_name = platform.system()
    if os_name == "Windows":
        from build_windows_release import main as build_windows_release

        build_windows_release()
        return
    validate_build_architecture(os_name)
    label = platform_label(os_name)

    run_pyinstaller()
    output_dir = assemble_release_folder(label)
    archive = create_runtime_zip(output_dir)

    print(f"Built {output_dir}")
    print(f"Built {archive}")


def platform_label(os_name: str) -> str:
    if os_name == "Windows":
        return "Windows-x64"
    if os_name == "Darwin":
        return "macOS"
    if os_name == "Linux":
        return "Linux"

    raise SystemExit(f"Unsupported build platform: {os_name}")


def validate_build_architecture(
    os_name: str,
    machine: str | None = None,
) -> None:
    """Prevent a non-x64 Windows binary from receiving the x64 release label."""
    if os_name != "Windows":
        return
    detected = (machine or platform.machine()).lower()
    if detected not in {"amd64", "x86_64"}:
        raise SystemExit(
            f"Windows-x64 release requires an x64 Python interpreter; found {detected}."
        )


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


def assemble_release_folder(label: str) -> Path:
    if not DIST_APP_DIR.exists():
        raise SystemExit(f"Missing PyInstaller output: {DIST_APP_DIR}")

    output_dir = RELEASE_DIR / f"PrimelockGIS-{label}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    shutil.copytree(DIST_APP_DIR, output_dir)
    shutil.copytree(PROJECT_ROOT / "data", output_dir / "data")
    copy_launchers(label, output_dir)
    return output_dir


def create_runtime_zip(output_dir: Path) -> Path:
    """Create an extract-and-run ZIP containing the runtime folder."""
    archive = output_dir.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    created = shutil.make_archive(
        str(archive.with_suffix("")),
        "zip",
        root_dir=output_dir.parent,
        base_dir=output_dir.name,
    )
    return Path(created)


def copy_launchers(label: str, output_dir: Path) -> None:
    if label.startswith("Windows"):
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
