"""Cross-platform terminal session facade."""

import sys

from primelock_gis.ui.terminal.backends import create_terminal_backend
from primelock_gis.ui.terminal.backends.base import TerminalBackend
from primelock_gis.ui.terminal.events import TerminalEvent

ENTER_ALTERNATE_SCREEN = "\x1b[?1049h"
LEAVE_ALTERNATE_SCREEN = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
ENABLE_MOUSE = "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
DISABLE_MOUSE = "\x1b[?1006l\x1b[?1002l\x1b[?1000l"


class TerminalSession:
    """Own platform console state and normalized input for one UI session."""

    def __init__(
        self,
        backend: TerminalBackend | None = None,
        stdin=None,
        stdout=None,
        platform_name: str | None = None,
        **backend_options,
    ) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.backend = backend or create_terminal_backend(
            platform_name=platform_name,
            stdin=self.stdin,
            stdout=self.stdout,
            **backend_options,
        )
        self._entered = False
        self._alternate_screen = False
        self._cursor_hidden = False
        self._mouse_enabled = False

    @property
    def diagnostic(self) -> str | None:
        """Return a feature-degradation or cleanup diagnostic, if any."""
        return self.backend.diagnostic

    @property
    def supports_mouse(self) -> bool:
        return self.backend.supports_mouse

    @property
    def supports_resize_events(self) -> bool:
        return self.backend.supports_resize_events

    def __enter__(self) -> "TerminalSession":
        self.backend.enter()
        self._entered = True
        try:
            if self.backend.supports_ansi:
                self._alternate_screen = True
                self._write(ENTER_ALTERNATE_SCREEN)
                self._cursor_hidden = True
                self._write(HIDE_CURSOR)
            if self.backend.supports_mouse:
                self._mouse_enabled = True
                self._write(ENABLE_MOUSE)
        except BaseException as enter_error:
            cleanup_errors = self._cleanup_display_state()
            try:
                self.backend.exit()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            finally:
                self._reset_state()
            if cleanup_errors and hasattr(enter_error, "add_note"):
                enter_error.add_note(
                    "Terminal rollback also failed: "
                    + "; ".join(str(error) for error in cleanup_errors)
                )
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        cleanup_errors: list[BaseException] = []
        cleanup_errors.extend(self._cleanup_display_state())

        try:
            if self._entered:
                self.backend.exit()
        except BaseException as error:
            cleanup_errors.append(error)
        finally:
            self._reset_state()

        if cleanup_errors:
            if exc_value is not None and hasattr(exc_value, "add_note"):
                exc_value.add_note(
                    "Terminal cleanup also failed: "
                    + "; ".join(str(error) for error in cleanup_errors)
                )
            elif exc_value is None:
                raise cleanup_errors[0]
        return False

    def read_event(self, timeout: float = 0.05) -> TerminalEvent | None:
        """Read one event from the active platform backend."""
        return self.backend.read_event(timeout)

    def _write(self, text: str) -> None:
        self.stdout.write(text)
        self.stdout.flush()

    def _cleanup_display_state(self) -> list[BaseException]:
        errors: list[BaseException] = []
        actions = (
            (self._mouse_enabled, DISABLE_MOUSE),
            (self._cursor_hidden, SHOW_CURSOR),
            (self._alternate_screen, LEAVE_ALTERNATE_SCREEN),
        )
        for enabled, sequence in actions:
            if not enabled:
                continue
            try:
                self._write(sequence)
            except BaseException as error:
                errors.append(error)
        return errors

    def _reset_state(self) -> None:
        self._entered = False
        self._alternate_screen = False
        self._cursor_hidden = False
        self._mouse_enabled = False
