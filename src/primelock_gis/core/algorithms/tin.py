"""Algorithms for generating TIN models."""
from primelock_gis.core.models.tin import TinVertex, TinTriangle, TinModel
from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.geometry import circumcircle_contains


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


def create_super_triangle(vertices: list[TinVertex]) -> tuple[list[TinVertex], TinTriangle]:
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

    # Robustness against the very thin or very small triangles.
    if span == 0:
        raise ValueError("Cannot create a TIN from identical point coordinates")

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    # Negative vertex IDs allow to easily delete the super triangles at the end
    p1 = TinVertex(id=-1, x=center_x, y=center_y + 3 * span, z=0.0,)
    p2 = TinVertex(id=-2, x=center_x - 3 * span, y=center_y - 3 * span, z=0.0)
    p3 = TinVertex(id=-3, x=center_x + 3 * span, y=center_y - 3 * span, z=0.0)

    super_triangle = TinTriangle(id=0, vertex_ids=(p1.id, p2.id, p3.id))

    return [p1, p2, p3], super_triangle


def build_tin_from_points(points: list[SpecialPoint]) -> TinModel:
    """Build a TIN model from sample points."""

    if len(points) < 3:
        raise ValueError("At least 3 vertices are required to build a TIN")

    real_vertices = points_to_tin_vertices(points)
    super_vertices, super_triangle = create_super_triangle(real_vertices)
    all_vertices = real_vertices + super_vertices

    vertex_by_id = _vertices_by_id(all_vertices)
    triangles = [super_triangle]

    next_triangle_id = 1

    for vertex in real_vertices:

        triangles, next_triangle_id = _add_vertex_to_triangulation(
            inserted_vertex = vertex,
            triangles = triangles,
            vertex_by_id = vertex_by_id,
            next_triangle_id = next_triangle_id
        )
    
    super_vertex_ids = {-1, -2, -3}
    final_triangles = _remove_super_triangle_triangles(triangles, super_vertex_ids)
    final_triangles = _renumber_triangles(final_triangles)

    return TinModel(
        vertices = real_vertices,
        triangles = final_triangles
    )



def _triangle_edges(triangle: TinTriangle) -> list[tuple[int, int]]:
    """Get the 3 undirected edges of a triangle."""
    a, b, c = triangle.vertex_ids
    # Sort the pairs to because (a, b) and (b, a) should be treated as the same pairs.
    edge_1 = tuple(sorted((a, b)))
    edge_2 = tuple(sorted((b, c)))
    edge_3 = tuple(sorted((c, a)))
    return [edge_1, edge_2, edge_3]


def _boundary_edges(bad_triangles) -> list[tuple[int, int]]:
    """From a group of “bad triangles”, find the outer boundary of the hole."""
    edge_counter = {}

    for triangle in bad_triangles:
        for edge in _triangle_edges(triangle):
            if edge not in edge_counter:
                edge_counter[edge] = 0

            edge_counter[edge] += 1

    boundary = []
    for edge, count in edge_counter.items():
        if count == 1:
            boundary.append(edge)

    return boundary


def _vertices_by_id(vertices: list[TinVertex]) -> dict[int, TinVertex]:
    """Return vertices indexed by their ID."""
    vertex_by_id = {}

    for vertex in vertices:
        vertex_by_id[vertex.id] = vertex

    return vertex_by_id


def _triangle_is_bad(triangle, inserted_vertex, vertex_by_id) -> bool:
    a_id, b_id, c_id = triangle.vertex_ids

    a = vertex_by_id[a_id]
    b = vertex_by_id[b_id]
    c = vertex_by_id[c_id]

    return circumcircle_contains(a, b, c, inserted_vertex)


def _add_vertex_to_triangulation(inserted_vertex, triangles, vertex_by_id, next_triangle_id):
    bad_triangles = []
    good_triangles = []

    for triangle in triangles:
        if _triangle_is_bad(triangle, inserted_vertex, vertex_by_id):
            bad_triangles.append(triangle)
        else:
            good_triangles.append(triangle)

    hole_edges = _boundary_edges(bad_triangles)
    new_triangles = []

    for edge in hole_edges:
        edge_start = edge[0]
        edge_end = edge[1]

        new_triangle = TinTriangle(
            id=next_triangle_id,
            vertex_ids=(edge_start, edge_end, inserted_vertex.id),
        )
        next_triangle_id += 1
        new_triangles.append(new_triangle)

    updated_triangles = good_triangles + new_triangles
    return updated_triangles, next_triangle_id


def _remove_super_triangle_triangles(triangles: list[TinTriangle], super_vertex_ids: set[int]) -> list[TinTriangle]:
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
    renumbered = []

    for index, triangle in enumerate(triangles):
        renumbered.append(
            TinTriangle(
                id=index,
                vertex_ids=triangle.vertex_ids,
            )
        )

    return renumbered