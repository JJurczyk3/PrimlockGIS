import pytest
from primelock_gis.core.algorithms.grid import create_grid_model_idw
from primelock_gis.core.models.vector import SpecialPoint


def test_create_grid_model_idw_from_four_corner_points():
    points = [
        SpecialPoint(1, "A", 0.0, 0.0, 10.0),
        SpecialPoint(2, "B", 10.0, 0.0, 20.0),
        SpecialPoint(3, "C", 0.0, 10.0, 30.0),
        SpecialPoint(4, "D", 10.0, 10.0, 40.0),
    ]

    grid = create_grid_model_idw(points, 2, 2)

    assert grid.x_min == 0.0
    assert grid.y_min == 0.0
    assert grid.x_max == 10.0
    assert grid.y_max == 10.0
    assert grid.x_divisions == 2
    assert grid.y_divisions == 2

    assert len(grid.node_values) == 3
    assert len(grid.node_values[0]) == 3

    expected_values = [
        [10.0, 18.333333333333336, 20.0],
        [21.666666666666668, 25.0, 28.333333333333336],
        [30.0, 31.666666666666668, 40.0],
    ]

    for actual_row, expected_row in zip(grid.node_values, expected_values):
        assert actual_row == pytest.approx(expected_row)


def test_create_grid_model_idw_center_is_average_when_corners_are_equally_distant():
    points = [
        SpecialPoint(1, "A", 0.0, 0.0, 10.0),
        SpecialPoint(2, "B", 10.0, 0.0, 20.0),
        SpecialPoint(3, "C", 0.0, 10.0, 30.0),
        SpecialPoint(4, "D", 10.0, 10.0, 40.0),
    ]

    grid = create_grid_model_idw(points, 2, 2)

    assert grid.node_values[1][1] == pytest.approx(25.0)