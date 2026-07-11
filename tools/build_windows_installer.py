"""Build the optional offline Inno Setup installer from the validated runtime."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping
from zipfile import ZipFile

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_windows_release import (  # noqa: E402
    PROJECT_ROOT,
    RELEASE_DIR,
    collect_source_files,
    create_zip,
    project_version,
    runtime_name,
    sha256_file,
    source_name,
    validate_runtime_tree,
    verify_archive,
    write_archive_manifest,
)

INNO_SPEC = PROJECT_ROOT / "packaging" / "inno" / "primelock_gis.iss"
INSTALLER_README = PROJECT_ROOT / "packaging" / "inno" / "INSTALLER_README.txt"
APP_ICON = PROJECT_ROOT / "packaging" / "icons" / "PrimelockGIS.ico"


def installer_name(version: str) -> str:
    return f"PrimelockGIS-Windows-x64-Setup-v{version}.exe"


def version_quad(version: str) -> str:
    """Convert a three- or four-part numeric project version to PE form."""
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or any(not part.isdigit() for part in parts):
        raise ValueError(f"Installer version must be numeric: {version}")
    return ".".join([*parts, *(["0"] * (4 - len(parts)))])


def inno_compiler_candidates(env: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    env = os.environ if env is None else env
    candidates: list[Path] = []
    configured = env.get("INNO_SETUP_ISCC")
    if configured:
        candidates.append(Path(configured))
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe"
        )
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        root = env.get(variable)
        if root:
            candidates.append(Path(root) / "Inno Setup 6" / "ISCC.exe")
    return tuple(candidates)


def find_inno_compiler(
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> Path:
    discovered = which("ISCC.exe") or which("ISCC")
    if discovered:
        return Path(discovered).resolve()
    for candidate in inno_compiler_candidates(env):
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit(
        "Inno Setup 6 compiler (ISCC.exe) was not found. Install the official "
        "JRSoftware.InnoSetup build package or set INNO_SETUP_ISCC."
    )


def build_iscc_command(
    compiler: Path,
    *,
    version: str,
    runtime_root: Path,
    release_dir: Path,
) -> tuple[str, ...]:
    return (
        str(compiler),
        "/Qp",
        f"/DMyAppVersion={version}",
        f"/DMyAppVersionQuad={version_quad(version)}",
        f"/DRuntimeRoot={runtime_root.resolve()}",
        f"/DReleaseDir={release_dir.resolve()}",
        f"/DInstallerReadme={INSTALLER_README.resolve()}",
        f"/DAppIcon={APP_ICON.resolve()}",
        str(INNO_SPEC.resolve()),
    )


def refresh_source_archive(version: str) -> Path:
    """Keep the source ZIP synchronized with the installer build sources."""
    archive = RELEASE_DIR / f"{source_name(version)}.zip"
    create_zip(archive, source_name(version), collect_source_files())
    verify_archive(archive, source_name(version))
    write_archive_manifest(archive, RELEASE_DIR / "MANIFEST-Source.txt")
    return archive


def validate_runtime_archive_matches_tree(
    runtime_root: Path,
    runtime_archive: Path,
    top_level: str,
) -> None:
    """Require the portable ZIP to contain the exact validated runtime tree."""
    verify_archive(runtime_archive, top_level)
    expected = {
        path.relative_to(runtime_root).as_posix(): (
            path.stat().st_size,
            sha256_file(path),
        )
        for path in runtime_root.rglob("*")
        if path.is_file()
    }
    actual: dict[str, tuple[int, str]] = {}
    prefix = f"{top_level}/"
    with ZipFile(runtime_archive) as zipped:
        for info in zipped.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise RuntimeError(
                    f"Portable ZIP entry is outside {top_level}: {info.filename}"
                )
            relative = info.filename.removeprefix(prefix)
            digest = hashlib.sha256()
            with zipped.open(info) as file:
                for block in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(block)
            actual[relative] = (info.file_size, digest.hexdigest().upper())

    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        changed = sorted(
            path
            for path in set(actual) & set(expected)
            if actual[path] != expected[path]
        )
        raise RuntimeError(
            "Portable ZIP does not match the validated runtime tree: "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )


def write_release_checksums(artifacts: tuple[Path, ...]) -> None:
    """Rewrite release hashes/sizes from the explicit delivery artifact set."""
    for path in artifacts:
        if not path.is_file():
            raise RuntimeError(f"Missing release artifact: {path}")
    (RELEASE_DIR / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in artifacts),
        encoding="ascii",
        newline="\n",
    )
    (RELEASE_DIR / "ARCHIVE_SIZES.txt").write_text(
        "".join(
            f"{path.stat().st_size} bytes  "
            f"{path.stat().st_size / (1024 * 1024):.2f} MiB  {path.name}\n"
            for path in artifacts
        ),
        encoding="ascii",
        newline="\n",
    )


def write_installer_manifest(installer: Path, runtime_archive: Path) -> None:
    rows = [
        "PRIMELOCK GIS OPTIONAL INSTALLER BUILD MANIFEST",
        "",
        f"installer={installer.name}",
        f"installer_bytes={installer.stat().st_size}",
        f"installer_sha256={sha256_file(installer)}",
        f"input_runtime_archive={runtime_archive.name}",
        f"input_runtime_sha256={sha256_file(runtime_archive)}",
        "install_scope=per-user",
        "network_dependencies=none",
        "code_signing=not configured",
    ]
    (RELEASE_DIR / "MANIFEST-Installer.txt").write_text(
        "\n".join(rows) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    version = project_version()
    runtime_root = RELEASE_DIR / runtime_name(version)
    runtime_archive = RELEASE_DIR / f"{runtime_name(version)}.zip"
    if not runtime_archive.is_file():
        raise SystemExit(
            "Validated portable ZIP is missing. Run tools\\build_windows_release.py first."
        )
    if not APP_ICON.is_file():
        raise SystemExit(f"Application icon is missing: {APP_ICON}")
    validate_runtime_tree(runtime_root)
    validate_runtime_archive_matches_tree(
        runtime_root,
        runtime_archive,
        runtime_name(version),
    )
    compiler = find_inno_compiler()
    installer = RELEASE_DIR / installer_name(version)
    if installer.exists():
        installer.unlink()

    subprocess.run(
        build_iscc_command(
            compiler,
            version=version,
            runtime_root=runtime_root,
            release_dir=RELEASE_DIR,
        ),
        cwd=PROJECT_ROOT,
        check=True,
    )
    if not installer.is_file() or installer.stat().st_size == 0:
        raise RuntimeError(f"Inno Setup did not produce {installer}")

    source_archive = refresh_source_archive(version)
    artifacts = (runtime_archive, installer, source_archive)
    write_release_checksums(artifacts)
    write_installer_manifest(installer, runtime_archive)
    print(f"Built optional installer: {installer}")
    print(f"Portable ZIP retained: {runtime_archive}")
    print(f"Updated source ZIP: {source_archive}")


if __name__ == "__main__":
    main()
