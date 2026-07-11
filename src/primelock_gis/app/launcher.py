"""One-click Windows launch orchestration and runtime diagnostics."""

from __future__ import annotations

import ctypes
import os
import secrets
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from primelock_gis import __version__
from primelock_gis.i18n import Language, resolve_language, tr

LOOPBACK_HOST = "127.0.0.1"
VIEWER_TITLE = "Primelock GIS - Viewer"
SUPPORT_TITLE = "Primelock GIS - Support / Control"
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
CREATE_NEW_PROCESS_GROUP = getattr(
    subprocess,
    "CREATE_NEW_PROCESS_GROUP",
    0x00000200,
)


class LaunchError(RuntimeError):
    """Raised when the application windows cannot be launched safely."""


@dataclass(frozen=True)
class ChildLaunch:
    role: str
    title: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class LaunchPlan:
    app_directory: Path
    host: str
    port: int
    session_token: str
    language: Language
    viewer: ChildLaunch
    support: ChildLaunch


@dataclass(frozen=True)
class LaunchResult:
    method: str
    port: int
    process_ids: tuple[int, ...]


def runtime_command(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
) -> tuple[str, ...]:
    """Return the command prefix for this frozen or source runtime."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    executable_path = str(Path(executable or sys.executable).resolve())
    if frozen:
        return (executable_path,)
    return (executable_path, "-m", "primelock_gis")


def runtime_directory(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
    source_directory: str | Path | None = None,
) -> Path:
    """Return the directory that owns runtime data and launchers."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(executable or sys.executable).resolve().parent
    return Path(source_directory or Path.cwd()).resolve()


def bundled_resource_path(
    *parts: str,
    frozen: bool | None = None,
    bundle_directory: str | Path | None = None,
    source_directory: str | Path | None = None,
) -> Path:
    """Resolve a read-only bundled resource independently of the current CWD."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        base = Path(
            bundle_directory
            or getattr(sys, "_MEIPASS", None)
            or runtime_directory(frozen=True)
        )
    else:
        base = Path(source_directory or Path(__file__).resolve().parents[3])
    return base.resolve().joinpath(*parts)


def find_free_loopback_port() -> int:
    """Ask Windows for an unused TCP port bound only to IPv4 loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK_HOST, 0))
        return int(sock.getsockname()[1])


def ensure_loopback_port_available(
    port: int,
    *,
    language: str | None = None,
) -> None:
    """Fail clearly before launching if an explicitly requested port is occupied."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((LOOPBACK_HOST, port))
    except OSError as error:
        raise LaunchError(
            tr("launch.port_conflict", language=language, port=port)
        ) from error


def viewer_title(language: str | None = None) -> str:
    """Return the localized viewer window title."""
    return tr("title.viewer", language=language)


def support_title(language: str | None = None) -> str:
    """Return the localized support-panel window title."""
    return tr("title.support", language=language)


def build_launch_plan(
    base_command: Sequence[str],
    app_directory: str | Path,
    *,
    port: int,
    session_token: str,
    language: str | None = None,
) -> LaunchPlan:
    """Build viewer/support commands without applying shell quoting."""
    directory = Path(app_directory).resolve()
    selected_language = resolve_language(language)
    shared_arguments = (
        "--language",
        selected_language,
        "--port",
        str(port),
        f"--session-token={session_token}",
    )
    viewer = ChildLaunch(
        role="viewer",
        title=viewer_title(selected_language),
        command=tuple(base_command) + ("viewer",) + shared_arguments,
    )
    support = ChildLaunch(
        role="support",
        title=support_title(selected_language),
        command=(
            tuple(base_command) + ("support",) + shared_arguments + ("--manage-viewer",)
        ),
    )
    return LaunchPlan(
        app_directory=directory,
        host=LOOPBACK_HOST,
        port=port,
        session_token=session_token,
        language=selected_language,
        viewer=viewer,
        support=support,
    )


def find_windows_terminal(
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Locate Windows Terminal without requiring it as a dependency."""
    if env is None:
        env = os.environ
    if env.get("PRIMELOCK_GIS_NO_WINDOWS_TERMINAL") == "1":
        return None

    discovered = which("wt.exe") or which("wt")
    if discovered:
        return discovered

    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Microsoft" / "WindowsApps" / "wt.exe"
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass
    return None


def build_windows_terminal_command(
    windows_terminal: str | Path,
    plan: LaunchPlan,
) -> tuple[str, ...]:
    """Build one Windows Terminal command that opens two titled tabs."""
    directory = str(plan.app_directory)
    return (
        str(windows_terminal),
        "-w",
        "new",
        "new-tab",
        "--startingDirectory",
        directory,
        "--title",
        plan.viewer.title,
        "--suppressApplicationTitle",
        *plan.viewer.command,
        ";",
        "new-tab",
        "--startingDirectory",
        directory,
        "--title",
        plan.support.title,
        "--suppressApplicationTitle",
        *plan.support.command,
    )


def launch_windows_application(
    *,
    base_command: Sequence[str] | None = None,
    app_directory: str | Path | None = None,
    port: int | None = None,
    session_token: str | None = None,
    language: str | None = None,
    prefer_windows_terminal: bool = True,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
) -> LaunchResult:
    """Open the complete viewer/support application experience."""
    platform_name = platform_name or os.name
    selected_language = resolve_language(language, env=env)
    if platform_name != "nt":
        raise LaunchError(tr("launch.windows_only", language=selected_language))

    base_command = tuple(base_command or runtime_command())
    app_directory = Path(app_directory or runtime_directory()).resolve()
    if port is None:
        port = find_free_loopback_port()
    else:
        ensure_loopback_port_available(port, language=selected_language)
    session_token = session_token or secrets.token_urlsafe(24)
    plan = build_launch_plan(
        base_command,
        app_directory,
        port=port,
        session_token=session_token,
        language=selected_language,
    )

    windows_terminal = None
    if prefer_windows_terminal:
        windows_terminal = find_windows_terminal(env=env, which=which)
    if windows_terminal:
        command = build_windows_terminal_command(windows_terminal, plan)
        try:
            process = popen(command, cwd=plan.app_directory)
        except OSError:
            windows_terminal = None
        else:
            try:
                return_code = process.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                return LaunchResult("windows-terminal", plan.port, (process.pid,))
            except (AttributeError, OSError):
                return LaunchResult("windows-terminal", plan.port, (process.pid,))
            if return_code == 0:
                return LaunchResult("windows-terminal", plan.port, (process.pid,))
            windows_terminal = None

    creation_flags = CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP
    processes: list[subprocess.Popen] = []
    try:
        for child in (plan.viewer, plan.support):
            processes.append(
                popen(
                    child.command,
                    cwd=plan.app_directory,
                    creationflags=creation_flags,
                )
            )
    except OSError as error:
        for process in processes:
            try:
                process.terminate()
            except OSError:
                pass
        for process in processes:
            try:
                process.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
        raise LaunchError(
            tr(
                "launch.console_failure",
                language=selected_language,
                error=error,
            )
        ) from error

    return LaunchResult(
        "windows-console",
        plan.port,
        tuple(process.pid for process in processes),
    )


def set_console_title(title: str) -> None:
    """Set the current console/tab title when the host supports it."""
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetConsoleTitleW.argtypes = [ctypes.c_wchar_p]
        kernel32.SetConsoleTitleW.restype = ctypes.c_int32
        kernel32.SetConsoleTitleW(title)
        return
    if sys.stdout.isatty():
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()


def doctor_lines(
    *,
    app_directory: str | Path | None = None,
    base_command: Sequence[str] | None = None,
    platform_name: str | None = None,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    language: str | None = None,
) -> tuple[list[str], bool]:
    """Return lightweight offline launch diagnostics and overall health."""
    selected_language = resolve_language(language, env=env)
    directory = Path(app_directory or runtime_directory()).resolve()
    command = tuple(base_command or runtime_command())
    executable = Path(command[0])
    dataset = bundled_resource_path("data", "initial_coords.csv")
    platform_name = platform_name or os.name
    executable_ok = executable.is_file()
    dataset_ok = dataset.is_file()

    try:
        port = find_free_loopback_port()
        port_line = tr(
            "doctor.port_available",
            language=selected_language,
            port=port,
        )
        port_ok = True
    except OSError as error:
        port_line = tr(
            "doctor.port_failure",
            language=selected_language,
            error=error,
        )
        port_ok = False

    if platform_name == "nt":
        wt = find_windows_terminal(env=env, which=which)
        terminal_line = (
            tr("doctor.windows_terminal", language=selected_language, path=wt)
            if wt
            else tr("doctor.console_fallback", language=selected_language)
        )
    else:
        terminal_line = tr("doctor.windows_only", language=selected_language)

    ok_status = "正常" if selected_language == "zh-CN" else "OK  "
    fail_status = "失败" if selected_language == "zh-CN" else "FAIL"
    lines = [
        f"Primelock GIS {__version__}",
        tr(
            "doctor.runtime_directory",
            language=selected_language,
            directory=directory,
        ),
        tr(
            "doctor.executable",
            language=selected_language,
            status=ok_status if executable_ok else fail_status,
            path=executable,
        ),
        tr(
            "doctor.dataset",
            language=selected_language,
            status=ok_status if dataset_ok else fail_status,
            path=dataset,
        ),
        port_line,
        terminal_line,
    ]
    return lines, executable_ok and dataset_ok and port_ok
