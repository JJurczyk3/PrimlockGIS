"""Data models for contour generation and tracing."""

from dataclasses import dataclass
from typing import Literal

from primelock_gis.core.geometry import Point


GridEdgeKind = Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class GridEdgeKey:
    kind: GridEdgeKind
    row: int
    col: int


ContourEdgeKey = GridEdgeKey | tuple[int, int]


@dataclass
class ContourSegment:
    level: float
    start: Point
    end: Point
    start_edge: ContourEdgeKey
    end_edge: ContourEdgeKey


@dataclass
class ContourPolyline:
    level: float
    points: list[Point]
    closed: bool = False
