"""Scene object setup for Primlock GIS.

This module defines drawable objects for rendering GIS features.
describes WHAT should be drawn
"""

from dataclasses import dataclass, field
from .symbology import PointStyle, PolylineStyle, FillStyle, TextStyle


@dataclass
class DrawablePolygon:
    points: list[tuple[float, float]]
    style: "FillStyle"

@dataclass
class DrawablePolyline:
    points: list[tuple[float, float]]
    style: "PolylineStyle"

@dataclass
class DrawablePoint:
    x: float
    y: float
    style: "PointStyle"

@dataclass
class DrawableText:
    x: float
    y: float
    text: str
    style: "TextStyle"

@dataclass
class Scene:
    polygons: list[DrawablePolygon] = field(default_factory=list)
    polylines: list[DrawablePolyline] = field(default_factory=list)
    points: list[DrawablePoint] = field(default_factory=list)
    texts: list[DrawableText] = field(default_factory=list)
