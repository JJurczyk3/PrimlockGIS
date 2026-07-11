"""Vector and topology data models."""

from dataclasses import dataclass, field


@dataclass
class SpecialPoint:
    """A named 3D sample point used by interpolation and TIN generation."""

    id: int
    name: str
    x: float
    y: float
    z: float = 0.0
    outer_polygon: int = -1


@dataclass
class Node:
    """A topology node and its incident arc identifiers."""

    id: int
    x: float
    y: float
    z: float = 0.0
    arc_ids: list[int] = field(default_factory=list)


@dataclass
class Arc:
    """A directed topology arc between two nodes."""

    id: int
    start_node: int
    end_node: int
    intermediate_points: list[tuple[float, float]] = field(default_factory=list)
    left_polygon: int = -1
    right_polygon: int = -1


@dataclass
class Polygon:
    """A polygon represented by its boundary arc identifiers."""

    id: int
    arc_ids: list[int]
    outer_polygon: int = -1


@dataclass
class TopologyModel:
    """The node, arc, and polygon relationships for one topology."""

    nodes: list[Node] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)
    polygons: list[Polygon] = field(default_factory=list)
