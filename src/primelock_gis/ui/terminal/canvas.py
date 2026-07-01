"""A simple styled canvas for drawing characters in a terminal."""

from dataclasses import dataclass, field
from functools import lru_cache
import math


Direction = str

HORIZONTAL_EDGES = frozenset(("left", "right"))
VERTICAL_EDGES = frozenset(("up", "down"))

BRAILLE_DOT_MASKS = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (0, 3): 0x40,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (1, 3): 0x80,
}

UNICODE_LINE_CHARS = {
    frozenset(("left",)): "─",
    frozenset(("right",)): "─",
    HORIZONTAL_EDGES: "─",
    frozenset(("up",)): "│",
    frozenset(("down",)): "│",
    VERTICAL_EDGES: "│",
    frozenset(("right", "down")): "┌",
    frozenset(("left", "down")): "┐",
    frozenset(("right", "up")): "└",
    frozenset(("left", "up")): "┘",
    frozenset(("up", "down", "right")): "├",
    frozenset(("up", "down", "left")): "┤",
    frozenset(("left", "right", "down")): "┬",
    frozenset(("left", "right", "up")): "┴",
    frozenset(("left", "right", "up", "down")): "┼",
}

ANSI_BASIC_COLORS = [
    (0, 0, 0, 30),
    (128, 0, 0, 31),
    (0, 128, 0, 32),
    (128, 128, 0, 33),
    (0, 0, 128, 34),
    (128, 0, 128, 35),
    (0, 128, 128, 36),
    (192, 192, 192, 37),
]


@dataclass
class TerminalCell:
    char: str = " "
    foreground: str | None = None
    background: str | None = None
    line_edges: set[Direction] = field(default_factory=set)
    line_color: str | None = None
    line_style: str | None = None
    braille_dots: int = 0
    braille_color: str | None = None
    braille_style: str | None = None

    def reset(
        self,
        char: str,
        foreground: str | None = None,
        background: str | None = None,
    ) -> None:
        self.char = safe_cell_char(char)
        self.foreground = foreground
        self.background = background
        self.line_edges.clear()
        self.line_color = None
        self.line_style = None
        self.braille_dots = 0
        self.braille_color = None
        self.braille_style = None

    def set_line(
        self,
        edges: set[Direction],
        color: str | None,
        line_style: str,
    ) -> None:
        if (
            self.line_edges
            and self.line_color == color
            and self.line_style == line_style
        ):
            self.line_edges.update(edges)
        else:
            self.char = " "
            self.foreground = None
            self.line_edges = set(edges)
            self.line_color = color
            self.line_style = line_style
            self.braille_dots = 0
            self.braille_color = None
            self.braille_style = None

    def set_braille_dot(
        self,
        dot_mask: int,
        color: str | None,
        line_style: str,
    ) -> None:
        if (
            self.braille_dots
            and self.braille_color == color
            and self.braille_style == line_style
        ):
            self.braille_dots |= dot_mask
        else:
            self.char = " "
            self.foreground = None
            self.line_edges.clear()
            self.line_color = None
            self.line_style = None
            self.braille_dots = dot_mask
            self.braille_color = color
            self.braille_style = line_style

    def render_char(
        self,
        supports_unicode: bool = True,
        supports_braille: bool = True,
    ) -> str:
        if self.braille_dots:
            if supports_unicode and supports_braille:
                return chr(0x2800 + self.braille_dots)
            return "*"

        if not self.line_edges:
            return self.char

        edges = frozenset(self.line_edges)
        if supports_unicode:
            return UNICODE_LINE_CHARS.get(edges, "┼")

        if edges.issubset(HORIZONTAL_EDGES):
            return "-"
        if edges.issubset(VERTICAL_EDGES):
            return "|"
        return "+"

    def render_color(self) -> str | None:
        if self.braille_dots:
            return self.braille_color
        if self.line_edges:
            return self.line_color
        return self.foreground

    def render_background(self) -> str | None:
        return self.background


@dataclass
class TerminalCanvas:
    width: int
    height: int
    fill_char: str = " "
    cells: list[list[TerminalCell]] = field(init=False)

    # If the input dimensions are valid, build an empty canvas.
    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("Canvas width must be positive")
        if self.height <= 0:
            raise ValueError("Canvas height must be positive")

        self.clear()

    # Reset the whole canvas.
    def clear(self, fill_char: str | None = None) -> None:
        if fill_char is not None:
            self.fill_char = fill_char

        safe_fill = safe_cell_char(self.fill_char)
        if not hasattr(self, "cells"):
            self.cells = [
                [
                    TerminalCell(char=safe_fill)
                    for _ in range(self.width)
                ]
                for _ in range(self.height)
            ]
            return

        for row in self.cells:
            for cell in row:
                cell.reset(safe_fill)

    # Write one character to one terminal cell.
    def set_cell(
        self,
        x: int,
        y: int,
        char: str,
        foreground: str | None = None,
        background: str | None = None,
        preserve_background: bool = True,
    ) -> None:
        if not char:
            return

        if 0 <= x < self.width and 0 <= y < self.height:
            if preserve_background and background is None:
                background = self.cells[y][x].background
            self.cells[y][x].reset(char, foreground, background)

    def set_background_cell(
        self,
        x: int,
        y: int,
        background: str | None,
        char: str = " ",
    ) -> None:
        """Set one cell's background while leaving it available for overlays."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x].reset(char, background=background)

    # Write one mergeable line fragment to a terminal cell.
    def set_line_cell(
        self,
        x: int,
        y: int,
        edges: set[Direction],
        color: str | None = None,
        line_style: str = "solid",
    ) -> None:
        if not edges:
            return

        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x].set_line(edges, color, line_style)

    # Write one Braille sub-cell dot into a terminal cell.
    def set_braille_dot(
        self,
        x: int,
        y: int,
        sub_x: int,
        sub_y: int,
        color: str | None = None,
        line_style: str = "solid",
    ) -> None:
        dot_mask = BRAILLE_DOT_MASKS.get((sub_x, sub_y))
        if dot_mask is None:
            return

        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x].set_braille_dot(dot_mask, color, line_style)

    # Write a text label horizontally into the canvas.
    def write_text(
        self,
        x: int,
        y: int,
        text: str,
        foreground: str | None = None,
    ) -> None:
        if y < 0 or y >= self.height:
            return
        if x >= self.width:
            return

        if x < 0:
            text = text[abs(x):]
            x = 0

        available_width = self.width - x
        text = clip_text_to_width(text, available_width)

        for i, char in enumerate(text):
            valid_char = safe_cell_char(char)
            self.set_cell(x + i, y, valid_char, foreground)

    # Convert canvas grid into printable text.
    def to_string(self, capabilities=None) -> str:
        supports_unicode = True
        supports_braille = True
        if capabilities is not None:
            supports_unicode = capabilities.supports_unicode
            supports_braille = capabilities.supports_braille

        rows = []

        for row in self.cells:
            rendered = []
            active_foreground = None
            active_background = None

            for cell in row:
                color = cell.render_color()
                background = cell.render_background()
                color_code = color_to_ansi(color, capabilities)
                background_code = color_to_ansi(
                    background,
                    capabilities,
                    background=True,
                )

                if (
                    color_code != active_foreground
                    or background_code != active_background
                ):
                    if active_foreground is not None or active_background is not None:
                        rendered.append("\x1b[0m")
                    if background_code is not None:
                        rendered.append(background_code)
                    if color_code is not None:
                        rendered.append(color_code)
                    active_foreground = color_code
                    active_background = background_code

                rendered.append(cell.render_char(supports_unicode, supports_braille))

            if active_foreground is not None or active_background is not None:
                rendered.append("\x1b[0m")

            rows.append("".join(rendered))

        return "\n".join(rows)


# Return True if char is safe to put into one terminal cell.
def is_safe_cell_char(char: str) -> bool:
    if char == "":
        return False
    elif not isinstance(char, str):
        return False
    elif len(char) != 1:
        return False
    elif char in ("\n", "\t", "\r"):
        return False
    return True


# Return char if it is safe. Otherwise return fallback.
def safe_cell_char(char: str, fallback=" ") -> str:
    if is_safe_cell_char(char):
        return char
    else:
        return fallback


# Make sure text fits within max_width by truncating it if necessary.
def clip_text_to_width(text: str, available_width: int) -> str:
    if len(text) <= available_width:
        return text
    else:
        return text[:available_width]


def color_to_ansi(
    color: str | None,
    capabilities=None,
    background: bool = False,
) -> str | None:
    """Return an ANSI foreground sequence for a colour and terminal capability."""
    if color is None:
        return None

    if color == "#000000":
        return None

    supports_color = capabilities is not None and capabilities.supports_color
    supports_truecolor = (
        capabilities is not None
        and capabilities.supports_truecolor
    )
    return _color_to_ansi_cached(
        color,
        supports_color,
        supports_truecolor,
        background,
    )


@lru_cache(maxsize=256)
def _color_to_ansi_cached(
    color: str,
    supports_color: bool,
    supports_truecolor: bool,
    background: bool,
) -> str | None:
    """Return a cached ANSI colour sequence for repeated style colours."""
    if not supports_color:
        return None

    rgb = parse_hex_color(color)
    if rgb is None:
        return None

    red, green, blue = rgb
    if supports_truecolor:
        prefix = 48 if background else 38
        return f"\x1b[{prefix};2;{red};{green};{blue}m"

    ansi_code = nearest_basic_ansi_color(red, green, blue)
    if background:
        ansi_code += 10
    return f"\x1b[{ansi_code}m"


def parse_hex_color(color: str) -> tuple[int, int, int] | None:
    """Parse #RRGGBB colours used by rendering styles."""
    if len(color) != 7 or not color.startswith("#"):
        return None

    try:
        return (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
        )
    except ValueError:
        return None


def nearest_basic_ansi_color(red: int, green: int, blue: int) -> int:
    """Return the closest basic ANSI foreground colour code."""
    best_code = 37
    best_distance = math.inf

    for basic_red, basic_green, basic_blue, ansi_code in ANSI_BASIC_COLORS:
        distance = (
            (red - basic_red) ** 2
            + (green - basic_green) ** 2
            + (blue - basic_blue) ** 2
        )

        if distance < best_distance:
            best_distance = distance
            best_code = ansi_code

    return best_code
