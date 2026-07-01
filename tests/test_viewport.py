import pytest

from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.viewport import Viewport


def test_world_to_view():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=1000,
        view_height=500,
    )

    assert viewport.world_to_view(0.0, 0.0) == Point(0.0, 500.0)
    assert viewport.world_to_view(100.0, 100.0) == Point(1000.0, 0.0)
    assert viewport.world_to_view(50.0, 50.0) == Point(500.0, 250.0)


def test_view_to_world():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=1000,
        view_height=500,
    )

    assert viewport.view_to_world(0.0, 500.0) == Point(0.0, 0.0)
    assert viewport.view_to_world(1000.0, 0.0) == Point(100.0, 100.0)
    assert viewport.view_to_world(500.0, 250.0) == Point(50.0, 50.0)


def test_pan_shifts_world_bounds_without_changing_view_size():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=50.0,
        view_width=100,
        view_height=50,
    )

    panned = viewport.pan(dx_world=10.0, dy_world=-5.0)

    assert panned.world_min_x == 10.0
    assert panned.world_max_x == 110.0
    assert panned.world_min_y == -5.0
    assert panned.world_max_y == 45.0
    assert panned.view_width == 100
    assert panned.view_height == 50


def test_zoom_factor_above_one_zooms_in_around_anchor():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=100,
        view_height=100,
    )

    zoomed = viewport.zoom(
        factor=2.0,
        center_world_x=25.0,
        center_world_y=75.0,
    )

    assert zoomed.world_min_x == 12.5
    assert zoomed.world_max_x == 62.5
    assert zoomed.world_min_y == 37.5
    assert zoomed.world_max_y == 87.5


def test_zoom_rejects_non_positive_factor():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=100,
        view_height=100,
    )

    with pytest.raises(ValueError):
        viewport.zoom(
            factor=0.0,
            center_world_x=50.0,
            center_world_y=50.0,
        )


def test_resize_viewport_preserves_world_scale_and_center_when_widening():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=100,
        view_height=100,
    )

    resized = viewport.resize_viewport(new_width=200, new_height=100)

    assert resized.world_min_x == pytest.approx(-50.0)
    assert resized.world_max_x == pytest.approx(150.0)
    assert resized.world_min_y == pytest.approx(0.0)
    assert resized.world_max_y == pytest.approx(100.0)
    assert resized.view_width == 200
    assert resized.view_height == 100


def test_resize_viewport_preserves_world_scale_and_center_when_tallening():
    viewport = Viewport(
        world_min_x=0.0,
        world_min_y=0.0,
        world_max_x=100.0,
        world_max_y=100.0,
        view_width=100,
        view_height=100,
    )

    resized = viewport.resize_viewport(new_width=100, new_height=200)

    assert resized.world_min_x == pytest.approx(0.0)
    assert resized.world_max_x == pytest.approx(100.0)
    assert resized.world_min_y == pytest.approx(-50.0)
    assert resized.world_max_y == pytest.approx(150.0)
    assert resized.view_width == 100
    assert resized.view_height == 200
