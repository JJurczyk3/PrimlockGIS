"""Shared terminal keyboard and mouse input parsing."""

import re
from collections.abc import Callable

from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent, TerminalEvent

ESCAPE_READ_TIMEOUT = 0.10
SGR_MOUSE_RE = re.compile(r"^\x1b\[<(\d+);(\d+);(\d+)([Mm])$")
VT_KEY_SEQUENCES = {
    "\x1b[A": "up",
    "\x1b[B": "down",
    "\x1b[C": "right",
    "\x1b[D": "left",
    "\x1bOA": "up",
    "\x1bOB": "down",
    "\x1bOC": "right",
    "\x1bOD": "left",
    "\x1b[H": "home",
    "\x1b[F": "end",
    "\x1bOH": "home",
    "\x1bOF": "end",
    "\x1b[2~": "insert",
    "\x1b[3~": "delete",
    "\x1b[5~": "page_up",
    "\x1b[6~": "page_down",
}


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

    key = VT_KEY_SEQUENCES.get(sequence)
    if key is not None:
        return KeyEvent(key, raw_sequence=sequence)

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
        return MouseEvent(
            kind="release", x=x, y=y, button=button, raw_sequence=sequence
        )

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


def read_escape_suffix(
    read_next_char: Callable[[float], str | None],
    max_chars: int = 32,
) -> str:
    """Read the remainder of one VT escape sequence."""
    suffix = ""

    first = read_next_char(ESCAPE_READ_TIMEOUT)
    if first is None:
        return suffix

    suffix += first
    if first == "O":
        second = read_next_char(ESCAPE_READ_TIMEOUT)
        if second is not None:
            suffix += second
        return suffix

    if first != "[":
        return suffix

    second = read_next_char(ESCAPE_READ_TIMEOUT)
    if second is None:
        return suffix

    suffix += second
    if second == "M":
        for _ in range(3):
            char = read_next_char(ESCAPE_READ_TIMEOUT)
            if char is None:
                break

            suffix += char

        return suffix

    if second == "<":
        while len(suffix) < max_chars:
            char = read_next_char(ESCAPE_READ_TIMEOUT)
            if char is None:
                break

            suffix += char
            if char in "Mm":
                break

        return suffix

    while len(suffix) < max_chars:
        if _csi_sequence_complete(suffix):
            break

        char = read_next_char(ESCAPE_READ_TIMEOUT)
        if char is None:
            break

        suffix += char

    return suffix


def _csi_sequence_complete(suffix: str) -> bool:
    if suffix[-1:].isalpha() or suffix[-1:] == "~":
        return True

    return False


class VTInputReader:
    """Turn a non-blocking character reader into normalized terminal events."""

    def __init__(self, read_next_char: Callable[[float], str | None]) -> None:
        self.read_next_char = read_next_char

    def read_event(self, timeout: float = 0.05) -> TerminalEvent | None:
        sequence = self.read_next_char(timeout)
        if sequence is None:
            return None

        if sequence == "\x1b":
            sequence += read_escape_suffix(self.read_next_char)

        return parse_input_sequence(sequence)
