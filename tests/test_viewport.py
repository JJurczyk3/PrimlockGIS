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