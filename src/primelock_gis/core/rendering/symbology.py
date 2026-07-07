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
    line_type: str = "literal"

@dataclass
class TextStyle:
    color: str = "#000000"
    height: float = 10.0

@dataclass
class TerrainStyle:
    low_color: str = "#1E3A8A"
    low_mid_color: str = "#15803D"
    high_mid_color: str = "#EAB308"
    high_color: str = "#DC2626"
    opacity: float = 1.0
    background_color: str = "#0B1020"
    char: str = " "
