"""Standard GIS application structures"""
from dataclasses import dataclass, field

@dataclass
class SpecialPoint:
    id: int
    name: str
    x: float
    y: float
    z: float = 0.0
    outer_polygon: int = -1

@dataclass
class Node:
    id: int
    x: float
    y: float
    z: float = 0.0
    arc_ids: list[int] = field(default_factory=list)

@dataclass
class Arc:
    id: int
    start_node: int
    end_node: int
    intermediate_points: list[tuple[float, float]] = field(default_factory=list)
    left_polygon: int = -1
    right_polygon: int = -1

@dataclass
class Polygon:
    id: int
    arc_ids: list[int]
    outer_polygon: int = -1


@dataclass
class TopologyModel:
    nodes: list[Node] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)
    polygons: list[Polygon] = field(default_factory=list)
