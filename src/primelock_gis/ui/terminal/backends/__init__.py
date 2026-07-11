"""Select the terminal backend for the current operating system."""

import os
import sys

from primelock_gis.ui.terminal.backends.base import (
    TerminalBackend,
    TerminalBackendError,
)


def backend_kind_for_platform(platform_name: str | None = None) -> str:
    """Return the backend kind for an ``os.name`` value."""
    platform_name = platform_name or os.name
    if platform_name == "nt":
        return "windows"
    if platform_name == "posix":
        return "posix"
    raise TerminalBackendError(f"Unsupported terminal platform: {platform_name}")


def create_terminal_backend(
    platform_name: str | None = None,
    stdin=None,
    stdout=None,
    **backend_options,
) -> TerminalBackend:
    """Create the platform backend without importing the other OS implementation."""
    kind = backend_kind_for_platform(platform_name)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    if kind == "windows":
        from primelock_gis.ui.terminal.backends.windows import WindowsTerminalBackend

        return WindowsTerminalBackend(
            stdin=stdin,
            stdout=stdout,
            **backend_options,
        )

    from primelock_gis.ui.terminal.backends.posix import PosixTerminalBackend

    return PosixTerminalBackend(stdin=stdin, stdout=stdout, **backend_options)
