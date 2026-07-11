"""Interfaces and errors shared by terminal platform backends."""

from typing import Protocol

from primelock_gis.ui.terminal.events import TerminalEvent


class TerminalBackendError(RuntimeError):
    """Raised when an interactive terminal backend cannot be configured."""


class TerminalBackend(Protocol):
    supports_ansi: bool
    supports_mouse: bool
    supports_resize_events: bool
    diagnostic: str | None

    def enter(self) -> None:
        """Save and configure platform terminal state."""

    def exit(self) -> None:
        """Restore saved platform terminal state."""

    def read_event(self, timeout: float = 0.05) -> TerminalEvent | None:
        """Read one normalized event, or return None on timeout."""
