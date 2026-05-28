""" Terminal keyboard and mouse input parsing. """

import select
import sys

from primelock_gis.ui.terminal.events import KeyEvent


def read_key_event(timeout: float = 0.05) -> KeyEvent | None:
    """Read one key event if available."""
    readable, _, _ = select.select([sys.stdin], [], [], timeout)

    if not readable:
        return None

    char = sys.stdin.read(1)

    if char == "\x1b":
        sequence = char + sys.stdin.read(2)
        return KeyEvent(sequence)
    
    return KeyEvent(char)