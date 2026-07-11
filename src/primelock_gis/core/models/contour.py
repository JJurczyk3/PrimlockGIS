"""Data models for contour generation and tracing."""

from dataclasses import dataclass
from typing import Literal

from primelock_gis.core.geometry import Point

GridEdgeKind = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class GridEdgeKey:
    """A stable identifier for one horizontal or vertical grid edge."""

    kind: GridEdgeKind
    row: int
    col: int


ContourEdgeKey = GridEdgeKey | tuple[int, int]


@dataclass
class ContourSegment:
    """A raw contour segment connecting two model edges."""

    level: float
    start: Point
    end: Point
    start_edge: ContourEdgeKey
    end_edge: ContourEdgeKey


@dataclass
class ContourPolyline:
    """An ordered open or closed contour at a single elevation."""

    level: float
    points: list[Point]
    closed: bool = False
