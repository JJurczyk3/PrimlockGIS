"""Backend-independent drawable objects for GIS scenes."""

from dataclasses import dataclass, field
from typing import Literal

from primelock_gis.core.geometry import Point
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel

from .symbology import (
    PointStyle,
    PolylineStyle,
    TerrainStyle,
    TextStyle,
)

TerrainSurface = GridModel | TinModel
TerrainSource = Literal["grid", "tin"]


@dataclass
class DrawableTerrain:
    """A sampled elevation surface rendered as terrain colour."""

    surface: TerrainSurface
    style: TerrainStyle
    source: TerrainSource = "grid"
    layer: str = "terrain"
    visible: bool = True


@dataclass
class DrawablePolyline:
    """A styled polyline in world coordinates."""

    points: list[Point]
    style: PolylineStyle
    layer: str = "default"
    visible: bool = True


@dataclass
class DrawablePoint:
    """A styled point in world coordinates."""

    position: Point
    style: PointStyle
    layer: str = "default"
    visible: bool = True


@dataclass
class DrawableText:
    """Styled text anchored at a world coordinate."""

    position: Point
    text: str
    style: TextStyle
    layer: str = "default"
    visible: bool = True


@dataclass
class Scene:
    """Drawable layers in their rendering order."""

    terrains: list[DrawableTerrain] = field(default_factory=list)
    polylines: list[DrawablePolyline] = field(default_factory=list)
    points: list[DrawablePoint] = field(default_factory=list)
    texts: list[DrawableText] = field(default_factory=list)
