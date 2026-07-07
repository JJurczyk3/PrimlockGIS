"""
This module defines drawable objects for rendering GIS features.
It describes WHAT should be drawn, not HOW it should be drawn.
"""

from dataclasses import dataclass, field

from primelock_gis.core.geometry import Point
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel
from .symbology import (
    PointStyle,
    PolylineStyle,
    TextStyle,
    TerrainStyle,
)

TerrainSurface = GridModel | TinModel


@dataclass
class DrawableTerrain:
    surface: TerrainSurface
    style: TerrainStyle
    source: str = "grid"
    layer: str = "terrain"
    visible: bool = True

@dataclass
class DrawablePolyline:
    points: list[Point]
    style: PolylineStyle
    layer: str = "default"
    visible: bool = True

@dataclass
class DrawablePoint:
    position: Point
    style: PointStyle
    layer: str = "default"
    visible: bool = True

@dataclass
class DrawableText:
    position: Point
    text: str
    style: TextStyle
    layer: str = "default"
    visible: bool = True

@dataclass
class Scene:
    terrains: list[DrawableTerrain] = field(default_factory=list)
    polylines: list[DrawablePolyline] = field(default_factory=list)
    points: list[DrawablePoint] = field(default_factory=list)
    texts: list[DrawableText] = field(default_factory=list)
