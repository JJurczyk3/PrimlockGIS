import pytest

from primelock_gis.core.algorithms.grid import (
    create_empty_grid_model,
    create_grid_model_idw,
    densify_grid_model,
    get_point_bounds,
)
from primelock_gis.core.models.grid import GridModel
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


def test_grid_model_set_node_value_updates_checked_node():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [1.0, 2.0],
            [3.0, 4.0],
        ],
    )

    grid.set_node_value(1, 0, 9.5)

    assert grid.node_value(1, 0) == 9.5


def test_grid_model_set_node_value_rejects_out_of_bounds_node():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [1.0, 2.0],
            [3.0, 4.0],
        ],
    )

    with pytest.raises(ValueError):
        grid.set_node_value(2, 0, 9.5)


def test_grid_model_value_at_bilinearly_interpolates_world_point():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [10.0, 20.0],
            [30.0, 40.0],
        ],
    )

    assert grid.sample_at(5.0, 5.0) == pytest.approx(25.0)
    assert grid.value_at(5.0, 5.0) == pytest.approx(25.0)
    assert grid.value_at(10.0, 10.0) == pytest.approx(40.0)


def test_grid_model_value_at_rejects_points_outside_bounds():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [10.0, 20.0],
            [30.0, 40.0],
        ],
    )

    assert grid.sample_at(11.0, 5.0) is None
    with pytest.raises(ValueError, match="outside grid bounds"):
        grid.value_at(11.0, 5.0)


def test_densify_grid_model_handles_non_square_grid():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=20.0,
        x_divisions=1,
        y_divisions=2,
        node_values=[
            [1.0, 3.0],
            [5.0, 7.0],
            [9.0, 11.0],
        ],
    )

    dense = densify_grid_model(grid, x_splits=2, y_splits=3)

    assert dense.x_divisions == 2
    assert dense.y_divisions == 6
    assert len(dense.node_values) == 7
    assert len(dense.node_values[0]) == 3
    assert dense.node_value(0, 0) == 1.0
    assert dense.node_value(0, 2) == 3.0
    assert dense.node_value(3, 1) == 6.0
    assert dense.node_value(6, 2) == 11.0


def test_densify_grid_model_rejects_invalid_splits():
    grid = GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=10.0,
        y_max=10.0,
        x_divisions=1,
        y_divisions=1,
        node_values=[
            [1.0, 2.0],
            [3.0, 4.0],
        ],
    )

    with pytest.raises(ValueError):
        densify_grid_model(grid, x_splits=0, y_splits=1)
