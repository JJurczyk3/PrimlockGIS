"""Define styles for rendering GIS features
"""

from dataclasses import dataclass


@dataclass
class PointStyle:
    color: str = "#000000"
    char: str = "o"

@dataclass
class PolylineStyle:
    color: str = "#000000"
    width: float = 1.0
    char: str = "-"

@dataclass
class FillStyle:
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    char: str = " "

@dataclass
class TextStyle:
    color: str = "#000000"
    height: float = 10.0