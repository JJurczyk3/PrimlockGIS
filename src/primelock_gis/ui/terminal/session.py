""" Terminal session management. """

import sys
import termios
import tty

class TerminalSession:
    """Manage terminal mode for an interactive terminal UI."""

    def __init__(self) -> None:
        self.original_settings = None

    def __enter__(self) -> "TerminalSession":
        self.original_settings = termios.tcgetattr(sys.stdin)

        tty.setcbreak(sys.stdin.fileno())
        self._write("\x1b[?1049h")  # enter alternate screen
        self._write("\x1b[?25l")    # hide cursor

        # Enable mouse support.
        self._write("\x1b[?1000h")  # basic mouse press/release
        self._write("\x1b[?1002h")  # mouse drag
        self._write("\x1b[?1006h")  # SGR mouse mode

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # Disable mouse support.
        self._write("\x1b[?1006l")
        self._write("\x1b[?1002l")
        self._write("\x1b[?1000l")

        self._write("\x1b[?25h")  # show cursor
        self._write("\x1b[?1049l")  # leave alternate screen

        if self.original_settings is not None:
            termios.tcsetattr(
                sys.stdin,
                termios.TCSADRAIN,
                self.original_settings,
            )

    def _write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()