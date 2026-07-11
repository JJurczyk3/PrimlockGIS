# Standalone Packaging Guide

Primelock GIS is released on Windows as a PyInstaller one-folder console
application. The professor-facing runtime requires no Python, `uv`, pip,
PyInstaller, Git, administrator access, or internet connection.

## Windows Deliverables

For project version `0.1.1`, the release builder creates:

```text
release/
|-- PrimelockGIS-Windows-x64-v0.1.1/
|   |-- START_PRIMELOCK_GIS.bat
|   |-- 启动_PRIMELOCK_GIS_中文版.bat
|   |-- README_FIRST_先读我.txt
|   |-- 先读我_中文版.txt
|   |-- VERSION.txt
|   |-- THIRD_PARTY_NOTICES.txt
|   `-- app/
|       |-- PrimelockGIS.exe
|       `-- _internal/
|           `-- data/initial_coords.csv
|-- PrimelockGIS-Windows-x64-v0.1.1.zip
|-- PrimelockGIS-Windows-x64-Setup-v0.1.1.exe
|-- PrimelockGIS-Source-v0.1.1.zip
|-- SHA256SUMS.txt
|-- ARCHIVE_SIZES.txt
|-- MANIFEST-Runtime.txt
|-- MANIFEST-Source.txt
`-- BUNDLE_SIZE_REPORT.txt
```

The three delivery formats have different purposes:

- **Portable ZIP (primary and fallback):** extract and run; it changes no
  installation state and is the format to submit when only one runtime is
  accepted.
- **Installer (optional secondary format):** installs the same validated
  one-folder runtime per user, adds Start menu integration, offers an optional
  desktop shortcut, and supplies an uninstaller. It is fully offline.
- **Source ZIP:** reviewable Python source, build definitions, data, and
  documentation. It is not the professor-facing runtime and requires the
  documented development environment.

The runtime root deliberately exposes two clearly labelled language launchers:
the English launcher always passes `--language en`, and the Chinese launcher
always passes `--language zh-CN`. Advanced `viewer`, `support`, `launch`,
`doctor`, and `--version` modes remain available through
`app\PrimelockGIS.exe` without adding competing technical scripts.

## Reproducible Windows Build

Requirements on the build machine only:

- Windows x64;
- 64-bit Python 3.13 or newer;
- `uv`.
- Inno Setup 6 when building the optional installer.

PyInstaller `6.21.0` is pinned in the development dependency group and in
`uv.lock`. The specification uses one-folder mode, `console=True`, and
`upx=False`.

From the repository root, run:

```powershell
uv run python tools\build_windows_release.py
```

The older cross-platform entry point delegates to the same release builder on
Windows:

```powershell
uv run python tools\build_standalone.py
```

The lock file currently uses the Tsinghua PyPI mirror. A different index may
be selected on the build machine if necessary; the finished runtime never
accesses a package index or the internet.

The builder removes only the generated `build`, `dist`, and `release`
directories before each run. It validates the Python architecture, pinned
PyInstaller version, PE machine type, executable resources, runtime hygiene,
ZIP integrity, and single top-level archive folders.

## Optional Offline Installer

Build the portable release first. Then compile the installer from that exact
validated runtime tree:

```powershell
uv run python tools\build_windows_release.py
uv run python tools\build_windows_installer.py
```

The source-controlled Inno Setup definition is
`packaging\inno\primelock_gis.iss`. The wrapper locates Inno Setup 6, passes
the project version and absolute staging paths without shell quoting, refreshes
the source ZIP, and writes hashes for all three delivery artifacts.

The installer uses `PrivilegesRequired=lowest` and defaults to:

```text
%LOCALAPPDATA%\Programs\Primelock GIS
```

It installs no service, driver, firewall rule, updater, downloader, or machine-
wide environment change. The Start menu and optional desktop shortcuts execute
`PrimelockGIS.exe launch`, which opens the complete viewer/support experience.
No signing step is configured; sign only through a legitimate certificate and
an explicitly reviewed release process.

External CSV files are never registered as installer-owned files. The
uninstaller removes the application and its shortcuts, not datasets selected
from Documents, Downloads, another drive, or another user-chosen location.
Primelock GIS currently creates no persistent configuration or application
logs. If those are added later, they must use a per-user location such as
`%LOCALAPPDATA%\Primelock GIS`, not the installation or dataset directory.

## Resource and Dataset Behavior

The default dataset is bundled by PyInstaller at:

```text
app\_internal\data\initial_coords.csv
```

Application resource lookup uses the source tree when running from source and
PyInstaller's bundle directory when frozen. It does not depend on the current
working directory. Bundled resources are treated as read-only.

External CSV datasets remain supported. In the Support / Control Admin panel,
use an absolute path, including paths containing spaces or Chinese characters:

```text
load dataset C:\Users\name\Documents\survey points.csv
```

Primelock GIS currently creates no persistent configuration, logs, or generated
output, so it does not need a writable application-data directory.

## Source Archive Whitelist

`PrimelockGIS-Source-v0.1.1.zip` is assembled only from this whitelist:

- `src/`, `data/`, `packaging/`, and `tools/`;
- `.python-version`, `pyproject.toml`, and `uv.lock`;
- `README.md`, `PACKAGING.md`, `design.md`, `THIRD_PARTY_NOTICES.txt`, and the
  English/Chinese coursework source guides.

The builder filters caches, virtual environments, Git/IDE state, bytecode,
logs, secrets, prior ZIPs, and generated build/release folders even if such
files exist under a whitelisted directory.

## Runtime Inspection Commands

Inspect the actual frozen executable from a different working directory:

```powershell
release\PrimelockGIS-Windows-x64-v0.1.1\app\PrimelockGIS.exe --version
release\PrimelockGIS-Windows-x64-v0.1.1\app\PrimelockGIS.exe doctor --language en
release\PrimelockGIS-Windows-x64-v0.1.1\app\PrimelockGIS.exe doctor --language zh-CN
```

Then extract the runtime ZIP to paths containing spaces and Chinese characters
and double-click either language launcher.

## Professor Instructions

```text
1. Extract the complete PrimelockGIS-Windows-x64-v0.1.1.zip archive.
2. Open the extracted PrimelockGIS-Windows-x64-v0.1.1 folder.
3. Double-click START_PRIMELOCK_GIS.bat (English) or 启动_PRIMELOCK_GIS_中文版.bat (中文).
4. Press q in Support / Control to close the complete application.
```

Windows Terminal is preferred when installed. Primelock GIS automatically
falls back to ordinary Windows console windows when it is unavailable.

## macOS and Linux

The existing POSIX launchers are preserved under `packaging/runtime/posix`.
Native macOS and Linux binaries must still be built separately on their target
operating systems because PyInstaller executables are not cross-platform.
