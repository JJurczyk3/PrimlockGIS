"""Terminal screen drawing helpers."""

import sys
import unicodedata

from primelock_gis.ui.terminal.theme import color_text


def character_width(character: str) -> int:
    """Return the terminal-cell width of one Unicode character."""
    if not character or unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in ("F", "W"):
        return 2
    return 1


def text_width(text: str) -> int:
    """Return terminal-cell width without interpreting ANSI sequences."""
    width = 0
    index = 0
    while index < len(text):
        if text[index] == "\x1b":
            index = _skip_ansi_sequence(text, index)
            continue
        width += character_width(text[index])
        index += 1
    return width


def clip_text(text: str, width: int) -> str:
    """Clip text to a terminal-cell width without splitting wide glyphs."""
    if width <= 0:
        return ""
    result: list[str] = []
    used = 0
    for character in text:
        next_width = character_width(character)
        if used + next_width > width:
            break
        result.append(character)
        used += next_width
    return "".join(result)


def _skip_ansi_sequence(text: str, index: int) -> int:
    """Return the first index after one ANSI control sequence."""
    index += 1
    if index < len(text) and text[index] == "[":
        index += 1
        while index < len(text) and not ("@" <= text[index] <= "~"):
            index += 1
        return min(len(text), index + 1)
    return index


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
        clip_text(instruction_text, width),
        instruction_color,
        capabilities,
    )
    info_text = color_text(
        clip_text(info_text, width),
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
