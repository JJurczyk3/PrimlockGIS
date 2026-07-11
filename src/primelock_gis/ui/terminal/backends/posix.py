"""POSIX terminal mode and input backend."""

import os
import sys

from primelock_gis.ui.terminal.backends.base import TerminalBackendError
from primelock_gis.ui.terminal.events import TerminalEvent
from primelock_gis.ui.terminal.input import VTInputReader


class PosixTerminalBackend:
    """Preserve the existing cbreak/select terminal implementation."""

    supports_ansi = True
    supports_mouse = True
    supports_resize_events = False
    diagnostic: str | None = None

    def __init__(self, stdin=None, stdout=None) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.original_settings = None
        self._reader = VTInputReader(self._read_next_char)

    def enter(self) -> None:
        if not self.stdin.isatty() or not self.stdout.isatty():
            raise TerminalBackendError(
                "Primelock GIS requires an interactive terminal; stdin or stdout is redirected."
            )

        import termios
        import tty

        self.original_settings = termios.tcgetattr(self.stdin)
        try:
            tty.setcbreak(self.stdin.fileno())
        except BaseException:
            try:
                termios.tcsetattr(
                    self.stdin,
                    termios.TCSADRAIN,
                    self.original_settings,
                )
            finally:
                self.original_settings = None
            raise

    def exit(self) -> None:
        if self.original_settings is None:
            return

        import termios

        try:
            termios.tcflush(self.stdin, termios.TCIFLUSH)
        finally:
            termios.tcsetattr(
                self.stdin,
                termios.TCSADRAIN,
                self.original_settings,
            )
            self.original_settings = None

    def read_event(self, timeout: float = 0.05) -> TerminalEvent | None:
        return self._reader.read_event(timeout)

    def _read_next_char(self, timeout: float) -> str | None:
        import select

        readable, _, _ = select.select([self.stdin.fileno()], [], [], timeout)
        if not readable:
            return None

        return os.read(self.stdin.fileno(), 1).decode("latin-1")
