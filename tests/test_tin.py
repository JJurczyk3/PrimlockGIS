import pytest

from primelock_gis.core.algorithms.tin import (
    _attach_triangle_neighbors,
    _boundary_edges,
    _remove_super_triangle_triangles,
    _triangle_edges,
    _vertices_by_id,
    build_tin_from_points,
    create_super_triangle,
    points_to_tin_vertices,
)
from primelock_gis.core.models.tin import TinModel, TinTriangle, TinVertex
from primelock_gis.core.models.vector import SpecialPoint


def test_points_to_tin_vertices_preserves_coordinates_and_source_ids():
    points = [
        SpecialPoint(10, "A", 1.0, 2.0, 3.0),
        SpecialPoint(20, "B", 4.0, 5.0, 6.0),
    ]

    vertices = points_to_tin_vertices(points)

    assert len(vertices) == 2

    assert vertices[0].id == 0
    assert vertices[0].x == 1.0
    assert vertices[0].y == 2.0
    assert vertices[0].z == 3.0
    assert vertices[0].source_point_id == 10

    assert vertices[1].id == 1
    assert vertices[1].source_point_id == 20


def test_create_super_triangle_returns_artificial_vertices_and_triangle():
    vertices = [
        TinVertex(id=0, x=0.0, y=0.0, z=1.0),
        TinVertex(id=1, x=10.0, y=0.0, z=2.0),
        TinVertex(id=2, x=5.0, y=10.0, z=3.0),
    ]

    super_vertices, super_triangle = create_super_triangle(vertices)

    assert len(super_vertices) == 3
    assert [vertex.id for vertex in super_vertices] == [-1, -2, -3]
    assert super_triangle.id == 0
    assert super_triangle.vertex_ids == (-1, -2, -3)


def test_triangle_edges_returns_sorted_undirected_edges():
    triangle = TinTriangle(
        id=0,
        vertex_ids=(3, 1, 2),
    )

    edges = _triangle_edges(triangle)

    assert edges == [
        (1, 3),
        (1, 2),
        (2, 3),
    ]


def test_tin_triangle_exposes_ordered_edges_and_default_topology_fields():
    triangle = TinTriangle(
        id=7,
        vertex_ids=(3, 1, 2),
    )

    assert triangle.edge_vertex_ids(0) == (3, 1)
    assert triangle.edge_vertex_ids(1) == (1, 2)
    assert triangle.edge_vertex_ids(2) == (2, 3)
    assert triangle.edge_key(0) == (1, 3)
    assert triangle.neighbor_triangle_ids == (None, None, None)
    assert triangle.edge_arc_ids == (None, None, None)
    assert triangle.containing_polygon_id is None


def test_tin_triangle_rejects_invalid_edge_index():
    triangle = TinTriangle(
        id=0,
        vertex_ids=(1, 2, 3),
    )

    with pytest.raises(ValueError):
        triangle.edge_vertex_ids(3)


def test_attach_triangle_neighbors_records_shared_edge_neighbors():
    triangles = [
        TinTriangle(id=0, vertex_ids=(0, 1, 2)),
        TinTriangle(id=1, vertex_ids=(1, 3, 2)),
    ]

    updated = _attach_triangle_neighbors(triangles)

    assert updated[0].neighbor_triangle_ids == (None, 1, None)
    assert updated[1].neighbor_triangle_ids == (None, None, 0)


def test_boundary_edges_removes_shared_internal_edge():
    bad_triangles = [
        TinTriangle(id=0, vertex_ids=(1, 2, 3)),
        TinTriangle(id=1, vertex_ids=(2, 4, 3)),
    ]

    edges = _boundary_edges(bad_triangles)

    assert set(edges) == {
        (1, 2),
        (1, 3),
        (2, 4),
        (3, 4),
    }


def test_vertices_by_id_returns_lookup_dictionary():
    vertices = [
        TinVertex(id=0, x=1.0, y=2.0, z=3.0),
        TinVertex(id=5, x=4.0, y=5.0, z=6.0),
    ]

    lookup = _vertices_by_id(vertices)

    assert lookup[0] is vertices[0]
    assert lookup[5] is vertices[1]


def test_tin_model_returns_vertex_triangle_and_edge_indexes():
    vertices = [
        TinVertex(id=0, x=0.0, y=0.0),
        TinVertex(id=1, x=10.0, y=0.0),
        TinVertex(id=2, x=0.0, y=10.0),
    ]
    triangles = [
        TinTriangle(id=4, vertex_ids=(0, 1, 2)),
    ]
    manual_tin = TinModel(vertices=vertices, triangles=triangles)

    assert manual_tin.vertex_by_id()[1] is vertices[1]
    assert manual_tin.triangle_by_id()[4] is triangles[0]
    assert manual_tin.unique_edge_keys() == {(0, 1), (1, 2), (0, 2)}


def test_tin_model_samples_value_inside_triangle():
    vertices = [
        TinVertex(id=0, x=0.0, y=0.0, z=10.0),
        TinVertex(id=1, x=10.0, y=0.0, z=20.0),
        TinVertex(id=2, x=0.0, y=10.0, z=30.0),
    ]
    tin = TinModel(
        vertices=vertices,
        triangles=[
            TinTriangle(id=0, vertex_ids=(0, 1, 2)),
        ],
    )

    assert tin.bounds() == (0.0, 0.0, 10.0, 10.0)
    assert tin.value_range() == (10.0, 30.0)
    assert tin.contains_xy(2.0, 3.0)
    assert tin.sample_at(2.0, 3.0) == pytest.approx(18.0)
    assert tin.value_at(2.0, 3.0) == pytest.approx(18.0)


def test_tin_model_rejects_value_outside_triangles():
    tin = TinModel(
        vertices=[
            TinVertex(id=0, x=0.0, y=0.0, z=10.0),
            TinVertex(id=1, x=10.0, y=0.0, z=20.0),
            TinVertex(id=2, x=0.0, y=10.0, z=30.0),
        ],
        triangles=[
            TinTriangle(id=0, vertex_ids=(0, 1, 2)),
        ],
    )

    assert not tin.contains_xy(9.0, 9.0)
    assert tin.sample_at(9.0, 9.0) is None
    with pytest.raises(ValueError, match="outside TIN bounds"):
        tin.value_at(9.0, 9.0)


def test_remove_super_triangle_triangles_removes_artificial_vertices():
    triangles = [
        TinTriangle(id=0, vertex_ids=(-1, 0, 1)),
        TinTriangle(id=1, vertex_ids=(0, 1, 2)),
        TinTriangle(id=2, vertex_ids=(2, -2, 3)),
    ]

    final_triangles = _remove_super_triangle_triangles(
        triangles,
        super_vertex_ids={-1, -2, -3},
    )

    assert len(final_triangles) == 1
    assert final_triangles[0].vertex_ids == (0, 1, 2)


def test_build_tin_from_three_points_creates_one_triangle():
    points = [
        SpecialPoint(1, "A", 0.0, 0.0, 10.0),
        SpecialPoint(2, "B", 10.0, 0.0, 20.0),
        SpecialPoint(3, "C", 0.0, 10.0, 30.0),
    ]

    tin = build_tin_from_points(points)

    assert len(tin.vertices) == 3
    assert len(tin.triangles) == 1

    triangle_vertex_ids = set(tin.triangles[0].vertex_ids)

    assert triangle_vertex_ids == {0, 1, 2}
    assert tin.triangles[0].neighbor_triangle_ids == (None, None, None)
    assert tin.triangles[0].edge_arc_ids == (None, None, None)


def test_build_tin_from_less_than_three_points_raises_error():
    points = [
        SpecialPoint(1, "A", 0.0, 0.0, 10.0),
        SpecialPoint(2, "B", 10.0, 0.0, 20.0),
    ]

    with pytest.raises(ValueError):
        build_tin_from_points(points)
