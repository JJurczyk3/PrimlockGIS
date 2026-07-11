"""Styles shared by backend-independent GIS drawables."""

from dataclasses import dataclass
from typing import Literal

LineType = Literal["literal", "solid", "braille", "dashed", "dotted"]


@dataclass
class PointStyle:
    """Colour and character used to draw a point."""

    color: str = "#000000"
    char: str = "o"


@dataclass
class PolylineStyle:
    """Colour, width, character, and rasterisation mode for a line."""

    color: str = "#000000"
    width: float = 1.0
    char: str = "-"
    line_type: LineType = "literal"


@dataclass
class TextStyle:
    """Colour and nominal height of a text label."""

    color: str = "#000000"
    height: float = 10.0


@dataclass
class TerrainStyle:
    """Four-stop terrain palette and background blending settings."""

    low_color: str = "#1E3A8A"
    low_mid_color: str = "#15803D"
    high_mid_color: str = "#EAB308"
    high_color: str = "#DC2626"
    opacity: float = 1.0
    background_color: str = "#0B1020"
    char: str = " "
