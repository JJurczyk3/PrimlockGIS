"""Build verified Windows runtime and source release archives."""

from __future__ import annotations

import hashlib
import platform
import shutil
import struct
import subprocess
import sys
import tomllib
from collections import defaultdict
from importlib.metadata import (
    PackageNotFoundError,
    distribution,
)
from importlib.metadata import version as package_version
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
DIST_APP_DIR = DIST_DIR / "PrimelockGIS"
RELEASE_DIR = PROJECT_ROOT / "release"
SPEC_PATH = PROJECT_ROOT / "packaging" / "pyinstaller" / "primelock_gis.spec"
WINDOWS_TEMPLATE_DIR = PROJECT_ROOT / "packaging" / "runtime" / "windows"
LICENSE_ASSET_DIR = PROJECT_ROOT / "packaging" / "licenses"
APP_ICON_PATH = PROJECT_ROOT / "packaging" / "icons" / "PrimelockGIS.ico"
PINNED_PYINSTALLER_VERSION = "6.21.0"
REQUIRED_LICENSE_NAMES = {
    "LIBFFI_LICENSE.txt",
    "OPENSSL_LICENSE.txt",
    "PYINSTALLER_COPYING.txt",
    "PYTHON_LICENSE.txt",
}
RUNTIME_TEMPLATE_FILES = (
    "START_PRIMELOCK_GIS.bat",
    "启动_PRIMELOCK_GIS_中文版.bat",
    "README_FIRST_先读我.txt",
    "先读我_中文版.txt",
)

SOURCE_ROOT_FILES = (
    ".python-version",
    "COURSEWORK_SOURCE_GUIDE.md",
    "COURSEWORK_SOURCE_GUIDE_ZH.md",
    "README.md",
    "PACKAGING.md",
    "THIRD_PARTY_NOTICES.txt",
    "design.md",
    "pyproject.toml",
    "uv.lock",
)
SOURCE_ROOT_DIRECTORIES = (
    "data",
    "packaging",
    "src",
    "tools",
)
FORBIDDEN_SOURCE_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__MACOSX",
    "__pycache__",
    "build",
    "dist",
    "release",
    "output",
    "temp",
    "tmp",
}
FORBIDDEN_SOURCE_SUFFIXES = {
    ".key",
    ".log",
    ".pem",
    ".pyc",
    ".pyo",
    ".zip",
}
FORBIDDEN_RUNTIME_PARTS = {
    "__pycache__",
    "hypothesis",
    "packaging",
    "pip",
    "setuptools",
}


def project_version(project_root: Path = PROJECT_ROOT) -> str:
    """Read the release version from the canonical project metadata."""
    with (project_root / "pyproject.toml").open("rb") as file:
        return str(tomllib.load(file)["project"]["version"])


def runtime_name(version: str) -> str:
    return f"PrimelockGIS-Windows-x64-v{version}"


def source_name(version: str) -> str:
    return f"PrimelockGIS-Source-v{version}"


def app_icon_name(version: str) -> str:
    """Return a versioned sidecar name that avoids stale Windows icon caches."""
    return f"PrimelockGIS-v{version}.ico"


def validate_windows_x64(
    *,
    system: str | None = None,
    machine: str | None = None,
    pointer_bits: int | None = None,
) -> None:
    """Refuse to produce a misleading Windows-x64 label."""
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    pointer_bits = pointer_bits or struct.calcsize("P") * 8
    if system != "Windows":
        raise SystemExit("The Windows release must be built on Windows.")
    if machine not in {"amd64", "x86_64"} or pointer_bits != 64:
        raise SystemExit(
            "Windows-x64 release requires a 64-bit x64 Python interpreter; "
            f"found machine={machine}, pointer_bits={pointer_bits}."
        )


def validate_build_versions(version: str) -> None:
    """Keep package, executable metadata, and build tooling versions synchronized."""
    init_text = (PROJECT_ROOT / "src" / "primelock_gis" / "__init__.py").read_text(
        encoding="utf-8"
    )
    if f'__version__ = "{version}"' not in init_text:
        raise SystemExit("pyproject.toml and primelock_gis.__version__ do not match.")
    version_info = (
        PROJECT_ROOT / "packaging" / "pyinstaller" / "version_info.txt"
    ).read_text(encoding="utf-8")
    numeric_parts = version.split(".")
    if not 1 <= len(numeric_parts) <= 4 or any(
        not part.isdigit() for part in numeric_parts
    ):
        raise SystemExit("Windows release versions must contain only numeric parts.")
    version_tuple = tuple(
        [*(int(part) for part in numeric_parts), *([0] * (4 - len(numeric_parts)))]
    )
    required_metadata = (
        f"filevers={version_tuple}",
        f"prodvers={version_tuple}",
        f"StringStruct('FileVersion', '{version}')",
        f"StringStruct('ProductVersion', '{version}')",
    )
    if any(fragment not in version_info for fragment in required_metadata):
        raise SystemExit(
            "PyInstaller fixed and string version metadata do not match the project "
            "version."
        )
    try:
        installed = package_version("pyinstaller")
    except PackageNotFoundError as error:
        raise SystemExit(
            "PyInstaller is not installed. Run this script through `uv run`."
        ) from error
    if installed != PINNED_PYINSTALLER_VERSION:
        raise SystemExit(
            f"PyInstaller {PINNED_PYINSTALLER_VERSION} is required; found {installed}."
        )


def _assert_generated_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT not in resolved.parents:
        raise RuntimeError(
            f"Refusing to modify path outside generated workspace: {resolved}"
        )
    return resolved


def remove_generated_path(path: Path) -> None:
    """Remove only a verified generated build path."""
    path = _assert_generated_path(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def clean_build_outputs() -> None:
    for path in (BUILD_DIR, DIST_DIR, RELEASE_DIR):
        remove_generated_path(path)
    RELEASE_DIR.mkdir(parents=True)


def run_pyinstaller() -> None:
    if not SPEC_PATH.is_file():
        raise SystemExit(f"Missing PyInstaller spec: {SPEC_PATH}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(SPEC_PATH),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def pe_machine(executable: Path) -> int:
    """Read the PE COFF machine identifier without external tools."""
    with executable.open("rb") as file:
        if file.read(2) != b"MZ":
            raise RuntimeError(f"Not a PE executable: {executable}")
        file.seek(0x3C)
        pe_offset = struct.unpack("<I", file.read(4))[0]
        file.seek(pe_offset)
        if file.read(4) != b"PE\0\0":
            raise RuntimeError(f"Invalid PE signature: {executable}")
        return struct.unpack("<H", file.read(2))[0]


def build_license_sources() -> dict[str, Path]:
    """Locate complete license texts for components shipped in the frozen app."""
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    try:
        pyinstaller_distribution = distribution("pyinstaller")
    except PackageNotFoundError as error:
        raise SystemExit(
            "Cannot locate the PyInstaller redistribution license."
        ) from error
    pyinstaller_license_entry = next(
        (
            entry
            for entry in (pyinstaller_distribution.files or ())
            if entry.name == "COPYING.txt" and "licenses" in entry.parts
        ),
        None,
    )
    if pyinstaller_license_entry is None:
        raise SystemExit("Cannot locate the PyInstaller COPYING.txt file.")
    pyinstaller_license = Path(
        pyinstaller_distribution.locate_file(pyinstaller_license_entry)
    )
    sources = {
        "PYTHON_LICENSE.txt": python_license,
        "PYINSTALLER_COPYING.txt": pyinstaller_license,
        "OPENSSL_LICENSE.txt": LICENSE_ASSET_DIR / "OPENSSL_LICENSE.txt",
        "LIBFFI_LICENSE.txt": LICENSE_ASSET_DIR / "LIBFFI_LICENSE.txt",
    }
    missing = [
        f"{name}: {path}" for name, path in sources.items() if not path.is_file()
    ]
    if missing:
        raise SystemExit(
            "Missing required redistribution license(s):\n" + "\n".join(missing)
        )
    return sources


def copy_build_licenses(app_dir: Path) -> None:
    destination = app_dir / "_licenses"
    destination.mkdir(parents=True)
    for name, source in build_license_sources().items():
        shutil.copy2(source, destination / name)


def assemble_runtime(version: str) -> Path:
    """Create the simple professor-facing runtime tree."""
    if not DIST_APP_DIR.is_dir():
        raise SystemExit(f"Missing PyInstaller output: {DIST_APP_DIR}")
    runtime_root = RELEASE_DIR / runtime_name(version)
    app_dir = runtime_root / "app"
    shutil.copytree(DIST_APP_DIR, app_dir)
    if not APP_ICON_PATH.is_file():
        raise SystemExit(f"Application icon is missing: {APP_ICON_PATH}")
    shutil.copy2(APP_ICON_PATH, app_dir / app_icon_name(version))
    copy_build_licenses(app_dir)
    for name in RUNTIME_TEMPLATE_FILES:
        shutil.copy2(WINDOWS_TEMPLATE_DIR / name, runtime_root / name)
    shutil.copy2(
        PROJECT_ROOT / "THIRD_PARTY_NOTICES.txt",
        runtime_root / "THIRD_PARTY_NOTICES.txt",
    )
    (runtime_root / "VERSION.txt").write_text(
        f"Primelock GIS {version}\nWindows x64 portable one-folder release\n",
        encoding="utf-8",
        newline="\n",
    )
    validate_runtime_tree(runtime_root)
    return runtime_root


def validate_runtime_tree(runtime_root: Path) -> None:
    expected_root_names = {
        *RUNTIME_TEMPLATE_FILES,
        "VERSION.txt",
        "THIRD_PARTY_NOTICES.txt",
        "app",
    }
    actual_root_names = {path.name for path in runtime_root.iterdir()}
    if actual_root_names != expected_root_names:
        raise RuntimeError(
            f"Unexpected runtime root content: {sorted(actual_root_names)}"
        )
    executable = runtime_root / "app" / "PrimelockGIS.exe"
    dataset = runtime_root / "app" / "_internal" / "data" / "initial_coords.csv"
    if not executable.is_file():
        raise RuntimeError("Frozen executable is missing from app/.")
    if pe_machine(executable) != 0x8664:
        raise RuntimeError("Frozen executable is not AMD64 (PE machine 0x8664).")
    if not dataset.is_file():
        raise RuntimeError("Default dataset is missing from PyInstaller resources.")
    icon_files = list((runtime_root / "app").glob("PrimelockGIS-v*.ico"))
    if len(icon_files) != 1:
        raise RuntimeError("Versioned application shortcut icon is missing from app/.")
    license_dir = runtime_root / "app" / "_licenses"
    actual_license_names = (
        {path.name for path in license_dir.iterdir() if path.is_file()}
        if license_dir.is_dir()
        else set()
    )
    if actual_license_names != REQUIRED_LICENSE_NAMES:
        raise RuntimeError(
            "Runtime redistribution licenses are incomplete: "
            f"{sorted(actual_license_names)}"
        )
    for path in runtime_root.rglob("*"):
        lowered_parts = {part.lower() for part in path.relative_to(runtime_root).parts}
        if lowered_parts & FORBIDDEN_RUNTIME_PARTS:
            raise RuntimeError(f"Development-only content entered runtime: {path}")
        if path.suffix.lower() in {".py", ".pyc", ".pyi", ".pyo"}:
            raise RuntimeError(f"Source/cache file entered runtime: {path}")
        if path.name == "py.typed":
            raise RuntimeError(f"Development type marker entered runtime: {path}")


def _source_path_allowed(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    if parts & FORBIDDEN_SOURCE_PARTS:
        return False
    if any(part.lower().endswith(".egg-info") for part in relative.parts):
        return False
    lowered_name = relative.name.lower()
    if lowered_name in {".ds_store", ".env"}:
        return False
    if lowered_name.startswith(".env."):
        return False
    return relative.suffix.lower() not in FORBIDDEN_SOURCE_SUFFIXES


def collect_source_files(project_root: Path = PROJECT_ROOT) -> list[tuple[Path, Path]]:
    """Collect source release files strictly from the public whitelist."""
    files: list[tuple[Path, Path]] = []
    for relative_text in SOURCE_ROOT_FILES:
        relative = Path(relative_text)
        source = project_root / relative
        if source.is_file() and _source_path_allowed(relative):
            files.append((source, relative))
    for directory_name in SOURCE_ROOT_DIRECTORIES:
        directory = project_root / directory_name
        if not directory.is_dir():
            continue
        for source in sorted(path for path in directory.rglob("*") if path.is_file()):
            relative = source.relative_to(project_root)
            if _source_path_allowed(relative):
                files.append((source, relative))
    return sorted(files, key=lambda item: item[1].as_posix())


def collect_tree_files(root: Path) -> list[tuple[Path, Path]]:
    return [
        (path, path.relative_to(root))
        for path in sorted(
            candidate for candidate in root.rglob("*") if candidate.is_file()
        )
    ]


def create_zip(
    archive: Path,
    top_level: str,
    files: list[tuple[Path, Path]],
) -> Path:
    """Create a ZIP whose entries all live under one explicit top-level folder."""
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as zipped:
        directory_entry = ZipInfo(f"{top_level}/")
        directory_entry.external_attr = 0o40775 << 16
        zipped.writestr(directory_entry, b"")
        for source, relative in files:
            zipped.write(source, f"{top_level}/{relative.as_posix()}")
    return archive


def verify_archive(archive: Path, expected_top_level: str) -> None:
    """Validate archive integrity, containment, and release hygiene."""
    with ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError(f"Corrupt ZIP member in {archive}")
        names = zipped.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError(f"Duplicate ZIP entries in {archive}")
        if not names:
            raise RuntimeError(f"Empty ZIP archive: {archive}")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"Unsafe ZIP path: {name}")
            if not path.parts or path.parts[0] != expected_top_level:
                raise RuntimeError(f"Unexpected ZIP root: {name}")
            if len(path.parts) > 1 and path.parts[1] == expected_top_level:
                raise RuntimeError(f"Duplicate nested project folder: {name}")
            if ":" in path.parts[0]:
                raise RuntimeError(f"Absolute drive path in ZIP: {name}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_archive_manifest(archive: Path, destination: Path) -> None:
    rows = ["SHA256  BYTES  PATH"]
    with ZipFile(archive) as zipped:
        for info in sorted(zipped.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            data = zipped.read(info.filename)
            digest = hashlib.sha256(data).hexdigest().upper()
            rows.append(f"{digest}  {info.file_size}  {info.filename}")
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def _format_size(size: int) -> str:
    return f"{size / (1024 * 1024):.2f} MiB"


def write_bundle_size_report(runtime_root: Path, destination: Path) -> None:
    files = [
        (path.stat().st_size, path)
        for path in runtime_root.rglob("*")
        if path.is_file()
    ]
    directory_totals: dict[Path, int] = defaultdict(int)
    for size, path in files:
        relative = path.relative_to(runtime_root)
        directory_totals[Path(".")] += size
        for parent in relative.parents:
            if parent != Path("."):
                directory_totals[parent] += size

    rows = ["PRIMELOCK GIS RUNTIME BUNDLE SIZE REPORT", "", "Largest directories:"]
    for directory, size in sorted(
        directory_totals.items(), key=lambda item: item[1], reverse=True
    )[:15]:
        label = runtime_root.name if directory == Path(".") else directory.as_posix()
        rows.append(f"{size:>12} bytes  {_format_size(size):>10}  {label}")
    rows.extend(["", "Largest files:"])
    for size, path in sorted(files, reverse=True)[:25]:
        rows.append(
            f"{size:>12} bytes  {_format_size(size):>10}  "
            f"{path.relative_to(runtime_root).as_posix()}"
        )
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def write_release_metadata(
    runtime_archive: Path, source_archive: Path, runtime_root: Path
) -> None:
    archives = (runtime_archive, source_archive)
    (RELEASE_DIR / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in archives),
        encoding="ascii",
        newline="\n",
    )
    (RELEASE_DIR / "ARCHIVE_SIZES.txt").write_text(
        "".join(
            f"{path.stat().st_size} bytes  {_format_size(path.stat().st_size)}  {path.name}\n"
            for path in archives
        ),
        encoding="ascii",
        newline="\n",
    )
    write_archive_manifest(runtime_archive, RELEASE_DIR / "MANIFEST-Runtime.txt")
    write_archive_manifest(source_archive, RELEASE_DIR / "MANIFEST-Source.txt")
    write_bundle_size_report(runtime_root, RELEASE_DIR / "BUNDLE_SIZE_REPORT.txt")


def main() -> None:
    validate_windows_x64()
    version = project_version()
    validate_build_versions(version)
    clean_build_outputs()
    run_pyinstaller()

    runtime_root = assemble_runtime(version)
    runtime_archive = create_zip(
        RELEASE_DIR / f"{runtime_name(version)}.zip",
        runtime_name(version),
        collect_tree_files(runtime_root),
    )
    source_archive = create_zip(
        RELEASE_DIR / f"{source_name(version)}.zip",
        source_name(version),
        collect_source_files(),
    )
    verify_archive(runtime_archive, runtime_name(version))
    verify_archive(source_archive, source_name(version))
    write_release_metadata(runtime_archive, source_archive, runtime_root)

    print(f"Built {runtime_archive}")
    print(f"Built {source_archive}")
    print(f"Release metadata: {RELEASE_DIR}")


if __name__ == "__main__":
    main()
