# Standalone Packaging Guide

This guide is for building offline application folders that can be given to a
teacher without requiring Python, `uv`, or package downloads on the teacher's
computer.

## Final Package Shape

Build each operating-system folder on that operating system:

```text
PrimelockGIS-Submission/
  Windows/
    PrimelockGIS.exe
    _internal/
    data/
    run_viewer.bat
    run_support.bat
  macOS/
    PrimelockGIS
    _internal/
    data/
    run_viewer.sh
    run_support.sh
  Linux/
    PrimelockGIS
    _internal/
    data/
    run_viewer.sh
    run_support.sh
  Source/
    README.md
    PACKAGING.md
    pyproject.toml
    uv.lock
    data/
    src/
    tests/
```

Only viewer/support launchers are included in the OS folders because the full
experience is the two-terminal viewer plus support panel.

## Why macOS and Linux Need Different Builds

macOS and Linux both have Unix-style shells, so they can use the same
`run_viewer.sh` and `run_support.sh` launcher scripts.

Their standalone binaries are not interchangeable:

- macOS uses Mach-O executables.
- Linux uses ELF executables.
- Python extension wheels, including dependencies such as `polars`, are built
  separately for each platform.

So the launcher scripts can be shared, but the packaged app folder must be
built separately on macOS and Linux.

## Windows Terminal Support

Kitty is not required on Windows. Use Windows Terminal or PowerShell for the
best result. The program enables Windows virtual-terminal mode at startup.

Keyboard controls and support-panel commands should work in standard Windows
terminals. Mouse support depends more on the terminal emulator, so it should be
tested on the target Windows machine.

## Build Tool

The project uses PyInstaller for standalone folders. Install PyInstaller only
on the build machine, not on the teacher's machine.

Mainland China mirror example:

```bash
uv run --with pyinstaller --index-url https://pypi.tuna.tsinghua.edu.cn/simple python tools/build_standalone.py
```

If PyInstaller is already installed in the active environment:

```bash
python tools/build_standalone.py
```

The build helper creates:

```text
release/Windows/
release/macOS/
release/Linux/
```

depending on the operating system where it is run.

## Build Steps

On macOS:

```bash
uv run --with pyinstaller python tools/build_standalone.py
```

On Windows PowerShell:

```powershell
uv run --with pyinstaller python tools\build_standalone.py
```

On Linux:

```bash
uv run --with pyinstaller python tools/build_standalone.py
```

Then copy the created OS folders into one final submission folder, alongside
the source folder.

## Teacher Run Instructions

Windows:

```text
run_viewer.bat
run_support.bat
```

macOS/Linux:

```bash
./run_viewer.sh
./run_support.sh
```

Open viewer and support in two separate terminal windows.
