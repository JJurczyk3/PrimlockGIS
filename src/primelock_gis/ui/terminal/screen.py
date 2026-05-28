""" Terminal screen driwing helpers. """

import sys


def write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()

def clear_screen() -> None:
    write("\x1b[2J")
    write("\x1b[H")

def move_cursor_home() -> None:
    write("\x1b[H")

def clear_line() -> None:
    write("\x1b[2K")

def draw_frame(text: str) -> None:
    move_cursor_home()
    write(text)

def draw_status_bar(text: str, row: int) -> None:
    write(f"\x1b[{row};1H")
    clear_line()
    write(text)