"""Terminal session management."""

import os
import sys

if os.name == "nt":
    import ctypes
else:
    import termios
    import tty


STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
ENABLE_ECHO_INPUT = 0x0004
ENABLE_LINE_INPUT = 0x0002
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200


class TerminalSession:
    """Manage terminal mode for an interactive terminal UI."""

    def __init__(self) -> None:
        self.original_settings = None
        self.original_input_mode: int | None = None
        self.original_output_mode: int | None = None

    def __enter__(self) -> "TerminalSession":
        if os.name == "nt":
            self._enter_windows_terminal_mode()
        else:
            self._enter_posix_terminal_mode()

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

        if os.name == "nt":
            self._restore_windows_terminal_mode()
            return

        termios.tcflush(sys.stdin, termios.TCIFLUSH)

        if self.original_settings is not None:
            termios.tcsetattr(
                sys.stdin,
                termios.TCSADRAIN,
                self.original_settings,
            )

    def _enter_posix_terminal_mode(self) -> None:
        self.original_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    def _enter_windows_terminal_mode(self) -> None:
        kernel32 = ctypes.windll.kernel32
        input_handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        output_handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        input_mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(input_handle, ctypes.byref(input_mode)):
            self.original_input_mode = input_mode.value
            next_input_mode = (
                input_mode.value
                | ENABLE_MOUSE_INPUT
                | ENABLE_WINDOW_INPUT
                | ENABLE_VIRTUAL_TERMINAL_INPUT
            )
            next_input_mode &= ~ENABLE_LINE_INPUT
            next_input_mode &= ~ENABLE_ECHO_INPUT
            kernel32.SetConsoleMode(input_handle, next_input_mode)

        output_mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(output_handle, ctypes.byref(output_mode)):
            self.original_output_mode = output_mode.value
            kernel32.SetConsoleMode(
                output_handle,
                output_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
            )

    def _restore_windows_terminal_mode(self) -> None:
        kernel32 = ctypes.windll.kernel32

        if self.original_input_mode is not None:
            input_handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
            kernel32.SetConsoleMode(input_handle, self.original_input_mode)

        if self.original_output_mode is not None:
            output_handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            kernel32.SetConsoleMode(output_handle, self.original_output_mode)

    def _write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()
