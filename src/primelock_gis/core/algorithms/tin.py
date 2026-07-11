"""Algorithms for generating TIN models."""

from collections import Counter
from dataclasses import replace
from math import isfinite

from primelock_gis.core.geometry import (
    EPS,
    circumcircle_contains,
    cross,
    distance_squared,
)
from primelock_gis.core.models.tin import TinEdgeKey, TinModel, TinTriangle, TinVertex
from primelock_gis.core.models.vector import SpecialPoint


def points_to_tin_vertices(points: list[SpecialPoint]) -> list[TinVertex]:
    """Convert sample points to TIN vertices."""
    vertices = []

    for index, point in enumerate(points):
        vertex = TinVertex(
            id=index,
            x=point.x,
            y=point.y,
            z=point.z,
            source_point_id=point.id,
        )
        vertices.append(vertex)
    return vertices


def create_super_triangle(
    vertices: list[TinVertex],
) -> tuple[list[TinVertex], TinTriangle]:
    """Create a large artificial triangle containing all vertices."""
    if len(vertices) < 3:
        raise ValueError("At least 3 vertices are required to build a TIN")

    x_min = min(vertex.x for vertex in vertices)
    y_min = min(vertex.y for vertex in vertices)
    x_max = max(vertex.x for vertex in vertices)
    y_max = max(vertex.y for vertex in vertices)

    width = x_max - x_min
    height = y_max - y_min
    span = max(width, height)

    if span == 0:
        raise ValueError("Cannot create a TIN from identical point coordinates")

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    # Negative vertex IDs make the artificial outer triangles easy to remove.
    p1 = TinVertex(id=-1, x=center_x, y=center_y + 3 * span, z=0.0)
    p2 = TinVertex(id=-2, x=center_x - 3 * span, y=center_y - 3 * span, z=0.0)
    p3 = TinVertex(id=-3, x=center_x + 3 * span, y=center_y - 3 * span, z=0.0)

    super_triangle = TinTriangle(id=0, vertex_ids=(p1.id, p2.id, p3.id))

    return [p1, p2, p3], super_triangle


def build_tin_from_points(points: list[SpecialPoint]) -> TinModel:
    """Build a Bowyer-Watson TIN from unique, non-collinear points."""
    _validate_tin_points(points)

    real_vertices = points_to_tin_vertices(points)
    super_vertices, super_triangle = create_super_triangle(real_vertices)
    all_vertices = real_vertices + super_vertices

    vertex_by_id = _vertices_by_id(all_vertices)
    triangles = [super_triangle]

    next_triangle_id = 1

    # Bowyer-Watson inserts points one at a time. Each insertion removes
    # triangles whose circumcircle contains the point, then retriangulates
    # the hole boundary with the new vertex.
    for vertex in real_vertices:
        triangles, next_triangle_id = _add_vertex_to_triangulation(
            inserted_vertex=vertex,
            triangles=triangles,
            vertex_by_id=vertex_by_id,
            next_triangle_id=next_triangle_id,
        )

    super_vertex_ids = {-1, -2, -3}
    final_triangles = _remove_super_triangle_triangles(triangles, super_vertex_ids)
    final_triangles = _renumber_triangles(final_triangles)
    final_triangles = _attach_triangle_neighbors(final_triangles)
    if not final_triangles:
        raise ValueError("TIN generation produced no triangles")

    return TinModel(
        vertices=real_vertices,
        triangles=final_triangles,
    )


def _validate_tin_points(points: list[SpecialPoint]) -> None:
    """Validate the geometric invariants required by triangulation."""
    if len(points) < 3:
        raise ValueError("At least 3 vertices are required to build a TIN")

    for point in points:
        if not all(isfinite(value) for value in (point.x, point.y, point.z)):
            raise ValueError("TIN point coordinates and elevations must be finite")

    for index, point in enumerate(points):
        if any(
            distance_squared(point, previous) <= EPS * EPS
            for previous in points[:index]
        ):
            raise ValueError("TIN points must have unique x/y coordinates")

    baseline_start, baseline_end = points[:2]
    if all(
        abs(cross(baseline_start, baseline_end, point)) <= EPS for point in points[2:]
    ):
        raise ValueError("Cannot build a TIN from collinear points")


def _triangle_edges(triangle: TinTriangle) -> list[TinEdgeKey]:
    """Get the 3 undirected edges of a triangle."""
    return [
        triangle.edge_key(0),
        triangle.edge_key(1),
        triangle.edge_key(2),
    ]


def _boundary_edges(bad_triangles: list[TinTriangle]) -> list[TinEdgeKey]:
    """From a group of bad triangles, find the outer boundary of the hole."""
    edge_counts = Counter(
        edge for triangle in bad_triangles for edge in _triangle_edges(triangle)
    )
    return [edge for edge, count in edge_counts.items() if count == 1]


def _vertices_by_id(vertices: list[TinVertex]) -> dict[int, TinVertex]:
    """Return vertices indexed by their ID."""
    return {vertex.id: vertex for vertex in vertices}


def _triangle_is_bad(
    triangle: TinTriangle,
    inserted_vertex: TinVertex,
    vertex_by_id: dict[int, TinVertex],
) -> bool:
    a_id, b_id, c_id = triangle.vertex_ids

    a = vertex_by_id[a_id]
    b = vertex_by_id[b_id]
    c = vertex_by_id[c_id]

    return circumcircle_contains(a, b, c, inserted_vertex)


def _add_vertex_to_triangulation(
    inserted_vertex: TinVertex,
    triangles: list[TinTriangle],
    vertex_by_id: dict[int, TinVertex],
    next_triangle_id: int,
) -> tuple[list[TinTriangle], int]:
    bad_triangles = []
    good_triangles = []

    for triangle in triangles:
        if _triangle_is_bad(triangle, inserted_vertex, vertex_by_id):
            bad_triangles.append(triangle)
        else:
            good_triangles.append(triangle)

    hole_edges = _boundary_edges(bad_triangles)
    new_triangles = []

    for edge_start, edge_end in hole_edges:
        new_triangle = TinTriangle(
            id=next_triangle_id,
            vertex_ids=(edge_start, edge_end, inserted_vertex.id),
        )
        next_triangle_id += 1
        new_triangles.append(new_triangle)

    updated_triangles = good_triangles + new_triangles
    return updated_triangles, next_triangle_id


def _remove_super_triangle_triangles(
    triangles: list[TinTriangle],
    super_vertex_ids: set[int],
) -> list[TinTriangle]:
    final_triangles = []

    for triangle in triangles:
        a_id, b_id, c_id = triangle.vertex_ids
        if (
            a_id in super_vertex_ids
            or b_id in super_vertex_ids
            or c_id in super_vertex_ids
        ):
            continue
        final_triangles.append(triangle)

    return final_triangles


def _renumber_triangles(triangles: list[TinTriangle]) -> list[TinTriangle]:
    """Assign contiguous IDs without discarding triangle metadata."""
    return [replace(triangle, id=index) for index, triangle in enumerate(triangles)]


def _attach_triangle_neighbors(triangles: list[TinTriangle]) -> list[TinTriangle]:
    """Populate neighbor ids across each ordered triangle edge.

    The lecture-note TIN structure stores only ordered vertex ids and neighbor
    triangle ids. Edges are implied by the vertex order:
    edge 0 = v0-v1, edge 1 = v1-v2, edge 2 = v2-v0.
    """
    edge_uses = _triangle_edge_uses(triangles)
    updated_triangles = []

    for triangle in triangles:
        neighbor_ids = []

        for edge_index in range(3):
            edge_key = triangle.edge_key(edge_index)
            neighbors = [
                other_triangle_id
                for other_triangle_id, _ in edge_uses[edge_key]
                if other_triangle_id != triangle.id
            ]
            neighbor_ids.append(min(neighbors) if neighbors else None)

        updated_triangles.append(
            TinTriangle(
                id=triangle.id,
                vertex_ids=triangle.vertex_ids,
                neighbor_triangle_ids=tuple(neighbor_ids),
                edge_arc_ids=triangle.edge_arc_ids,
                containing_polygon_id=triangle.containing_polygon_id,
            )
        )

    return updated_triangles


def _triangle_edge_uses(
    triangles: list[TinTriangle],
) -> dict[TinEdgeKey, list[tuple[int, int]]]:
    """Return edge key -> triangle/edge-index references."""
    edge_uses: dict[TinEdgeKey, list[tuple[int, int]]] = {}

    for triangle in triangles:
        for edge_index in range(3):
            edge_key = triangle.edge_key(edge_index)
            edge_uses.setdefault(edge_key, []).append((triangle.id, edge_index))

    return edge_uses
