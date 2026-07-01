""" Terminal screen driwing helpers. """

import shutil
import sys

from primelock_gis.ui.terminal.theme import color_text


def write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()

def clear_screen() -> None:
    write("\x1b[2J\x1b[H")

def move_cursor_home() -> None:
    write("\x1b[H")

def clear_line() -> None:
    write("\x1b[2K")

def draw_frame(text: str) -> None:
    move_cursor_home()
    write(text)

def draw_status_bar(text: str, row: int, width: int | None = None) -> None:
    if width is None:
        width = shutil.get_terminal_size().columns

    write(f"\x1b[{row};1H")
    clear_line()
    write(text[:width])


def present_frame(
    frame: str,
    instruction_text: str,
    info_text: str,
    instruction_row: int,
    info_row: int,
    width: int,
    instruction_color: str | None = None,
    info_color: str | None = None,
    capabilities=None,
) -> None:
    """Present a full viewer frame and status rows with one terminal flush."""
    instruction_text = color_text(
        instruction_text[:width],
        instruction_color,
        capabilities,
    )
    info_text = color_text(
        info_text[:width],
        info_color,
        capabilities,
    )
    output = (
        "\x1b[H"
        + frame
        + f"\x1b[{instruction_row};1H\x1b[2K"
        + instruction_text
        + f"\x1b[{info_row};1H\x1b[2K"
        + info_text
    )
    write(output)
