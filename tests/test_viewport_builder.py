import pytest
from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points


def test_initial_viewport_from_points_keeps_view_size():
    points = [
        Point(0, 0),
        Point(100, 100),
    ]

    viewport = initial_viewport_from_points(points, 80, 24)

    assert viewport.view_width == 80
    assert viewport.view_height == 24


def test_initial_viewport_from_points_rejects_empty_points():
    with pytest.raises(ValueError):
        initial_viewport_from_points([], 100, 100)