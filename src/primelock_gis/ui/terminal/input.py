""" Terminal keyboard and mouse input parsing. """

import os
import re
import select
import sys

from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent, TerminalEvent

ESCAPE_READ_TIMEOUT = 0.10
SGR_MOUSE_RE = re.compile(r"^\x1b\[<(\d+);(\d+);(\d+)([Mm])$")


def parse_input_sequence(sequence: str) -> TerminalEvent | None:
    """Parse one terminal input sequence into an event object."""
    if sequence == "":
        return None

    mouse_event = parse_sgr_mouse_sequence(sequence)
    if mouse_event is not None:
        return mouse_event

    mouse_event = parse_x10_mouse_sequence(sequence)
    if mouse_event is not None:
        return mouse_event

    if sequence == "\x1b":
        return KeyEvent("escape", raw_sequence=sequence)

    if len(sequence) == 1:
        return KeyEvent(sequence, raw_sequence=sequence)

    return KeyEvent(sequence, raw_sequence=sequence)


def parse_sgr_mouse_sequence(sequence: str) -> MouseEvent | None:
    """Parse an xterm SGR mouse event sequence."""
    match = SGR_MOUSE_RE.match(sequence)

    if match is None:
        return None

    code = int(match.group(1))
    x = int(match.group(2)) - 1
    y = int(match.group(3)) - 1
    final_char = match.group(4)

    button = code & 0b11

    if code & 0b1000000:
        kind = "wheel_up"
        if button == 1:
            kind = "wheel_down"
        return MouseEvent(kind=kind, x=x, y=y, button=None, raw_sequence=sequence)

    if final_char == "m":
        return MouseEvent(kind="release", x=x, y=y, button=button, raw_sequence=sequence)

    if code & 0b100000:
        return MouseEvent(kind="drag", x=x, y=y, button=button, raw_sequence=sequence)

    return MouseEvent(kind="press", x=x, y=y, button=button, raw_sequence=sequence)


def parse_x10_mouse_sequence(sequence: str) -> MouseEvent | None:
    """Parse an older xterm mouse event sequence.

    Modern terminals should use SGR mouse mode, but accepting this format makes
    click handling more resilient when a terminal ignores SGR mode.
    """
    if len(sequence) != 6 or not sequence.startswith("\x1b[M"):
        return None

    code = ord(sequence[3]) - 32
    x = ord(sequence[4]) - 33
    y = ord(sequence[5]) - 33
    button = code & 0b11

    if code & 0b1000000:
        kind = "wheel_up"
        if button == 1:
            kind = "wheel_down"
        return MouseEvent(kind=kind, x=x, y=y, button=None, raw_sequence=sequence)

    if button == 3:
        return MouseEvent(kind="release", x=x, y=y, button=None, raw_sequence=sequence)

    if code & 0b100000:
        return MouseEvent(kind="drag", x=x, y=y, button=button, raw_sequence=sequence)

    return MouseEvent(kind="press", x=x, y=y, button=button, raw_sequence=sequence)


def read_terminal_event(timeout: float = 0.05) -> TerminalEvent | None:
    """Read one terminal event if available."""
    readable, _, _ = select.select([sys.stdin.fileno()], [], [], timeout)

    if not readable:
        return None

    sequence = _read_stdin_char()

    if sequence == "\x1b":
        sequence += _read_escape_suffix()

    return parse_input_sequence(sequence)


def read_key_event(timeout: float = 0.05) -> KeyEvent | None:
    """Read one key event if available.

    Kept for callers that only understand keyboard input.
    """
    event = read_terminal_event(timeout)

    if isinstance(event, KeyEvent):
        return event

    return None


def _read_escape_suffix(max_chars: int = 32) -> str:
    suffix = ""

    first = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
    if first is None:
        return suffix

    suffix += first
    if first == "O":
        second = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
        if second is not None:
            suffix += second
        return suffix

    if first != "[":
        return suffix

    second = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
    if second is None:
        return suffix

    suffix += second
    if second == "M":
        for _ in range(3):
            char = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
            if char is None:
                break

            suffix += char

        return suffix

    if second == "<":
        while len(suffix) < max_chars:
            char = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
            if char is None:
                break

            suffix += char
            if char in "Mm":
                break

        return suffix

    while len(suffix) < max_chars:
        if _csi_sequence_complete(suffix):
            break

        char = _read_next_stdin_char(ESCAPE_READ_TIMEOUT)
        if char is None:
            break

        suffix += char

    return suffix


def _csi_sequence_complete(suffix: str) -> bool:
    if suffix[-1:].isalpha() or suffix[-1:] == "~":
        return True

    return False


def _read_next_stdin_char(timeout: float) -> str | None:
    readable, _, _ = select.select([sys.stdin.fileno()], [], [], timeout)

    if not readable:
        return None

    return _read_stdin_char()


def _read_stdin_char() -> str:
    return os.read(sys.stdin.fileno(), 1).decode("latin-1")
