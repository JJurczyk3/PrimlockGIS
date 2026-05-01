from primelock_gis.core.algorithms.grid import (
    create_empty_grid_model,
    create_grid_model_idw,
    get_point_bounds,
)
from primelock_gis.core.models.vector import SpecialPoint


def test_get_point_bounds():
    points = [SpecialPoint(1, "A", 0.0, 2.0), SpecialPoint(2, "B", 3.0, -1.0)]
    bounds = get_point_bounds(points)
    assert (bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y) == (0.0, -1.0, 3.0, 2.0)


def test_create_empty_grid_model_shape():
    points = [SpecialPoint(1, "A", 0.0, 0.0), SpecialPoint(2, "B", 2.0, 2.0)]
    grid = create_empty_grid_model(points, 2, 3)
    assert len(grid.node_values) == 4
    assert len(grid.node_values[0]) == 3


def test_create_grid_model_idw_returns_point_value_at_source():
    points = [SpecialPoint(1, "A", 0.0, 0.0, z=7.5), SpecialPoint(2, "B", 2.0, 2.0, z=10.0)]
    grid = create_grid_model_idw(points, 2, 2)
    assert grid.node_values[0][0] == 7.5


def test_create_grid_model_idw_preserves_known_corner_values():
    points = [
        SpecialPoint(id=1, name="A", x=0.0, y=0.0, z=10.0),
        SpecialPoint(id=2, name="B", x=10.0, y=0.0, z=20.0),
        SpecialPoint(id=3, name="C", x=0.0, y=10.0, z=30.0),
        SpecialPoint(id=4, name="D", x=10.0, y=10.0, z=40.0),
    ]
    grid = create_grid_model_idw(
        points=points,
        x_divisions=1,
        y_divisions=1,
    )
    assert grid.node_values[0][0] == 10.0
    assert grid.node_values[0][1] == 20.0
    assert grid.node_values[1][0] == 30.0
    assert grid.node_values[1][1] == 40.0
