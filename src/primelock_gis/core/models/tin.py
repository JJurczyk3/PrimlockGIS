"""Datastructures for TIN generation."""

from dataclasses import dataclass


@dataclass
class TinVertex:
    id: int
    x: float
    y: float
    z: float = 0.0
    source_point_id: int | None = None

@dataclass
class TinTriangle:
    id: int
    vertex_ids: tuple[int, int, int]
    '''
    # Neighbour across each implied edge:
    # edge 0 = v0-v1
    # edge 1 = v1-v2
    # edge 2 = v2-v0
    neighbor_triangle_ids: tuple[int | None, int | None, int | None] = (
        None, None, None)
    # GIS arc or boundary represented by each triangle edge.
    # None means ordinary internal triangulation edge.
    edge_arc_ids: tuple[int | None, int | None, int | None] = (
        None, None, None)
    # Larger polygon or region containing this triangle.
    containing_polygon_id: int | None = None
    '''

@dataclass
class TinModel:
    vertices: list[TinVertex]
    triangles: list[TinTriangle]
