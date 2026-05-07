from primelock_gis.core.algorithms.tin import points_to_tin_vertices
from primelock_gis.core.models.vector import SpecialPoint


def test_points_to_tin_vertices():
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