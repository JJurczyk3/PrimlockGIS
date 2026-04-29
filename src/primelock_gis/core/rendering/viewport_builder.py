"""Create viewports from GIS data."""

from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.viewport import Viewport


def initial_viewport_from_points(
    points: list[Point],
    view_width: int,
    view_height: int,
    padding: float = 0.05,
) -> Viewport:
    """Create an initial viewport that fits all points."""
    if not points:
        raise ValueError("Cannot create viewport from an empty point list")

    if view_width <= 0:
        raise ValueError("View width must be positive")

    if view_height <= 0:
        raise ValueError("View height must be positive")

    if padding < 0:
        raise ValueError("Padding cannot be negative")

    world_min_x = min(point.x for point in points)
    world_max_x = max(point.x for point in points)
    world_min_y = min(point.y for point in points)
    world_max_y = max(point.y for point in points)
    
    world_width = world_max_x - world_min_x
    world_height = world_max_y - world_min_y

    # Avoid zero-size viewport bounds to avoid division by 0.
    if world_width == 0:
        world_min_x -= 0.5
        world_max_x += 0.5
        world_width = 1.0

    if world_height == 0:
        world_min_y -= 0.5
        world_max_y += 0.5
        world_height = 1.0

    pad_x = world_width * padding
    pad_y = world_height * padding

    world_min_x -= pad_x
    world_max_x += pad_x
    world_min_y -= pad_y
    world_max_y += pad_y

    world_min_x, world_min_y, world_max_x, world_max_y = fit_bounds_to_view_aspect(
        world_min_x,
        world_min_y,
        world_max_x,
        world_max_y,
        view_width,
        view_height,
    )
    return Viewport(
        world_min_x=world_min_x,
        world_min_y=world_min_y,
        world_max_x=world_max_x,
        world_max_y=world_max_y,
        view_width=view_width,
        view_height=view_height,
    )


def fit_bounds_to_view_aspect(
    world_min_x: float,
    world_min_y: float,
    world_max_x: float,
    world_max_y: float,
    view_width: int,
    view_height: int,
) -> tuple[float, float, float, float]:
    """Expand world bounds so they match the view aspect ratio."""
    world_width = world_max_x - world_min_x
    world_height = world_max_y - world_min_y

    world_center_x = (world_min_x + world_max_x) / 2
    world_center_y = (world_min_y + world_max_y) / 2

    world_aspect = world_width / world_height
    view_aspect = view_width / view_height

    if world_aspect < view_aspect:
        new_width = world_height * view_aspect
        half_width = new_width / 2

        world_min_x = world_center_x - half_width
        world_max_x = world_center_x + half_width

    elif world_aspect > view_aspect:
        new_height = world_width / view_aspect
        half_height = new_height / 2

        world_min_y = world_center_y - half_height
        world_max_y = world_center_y + half_height

    return world_min_x, world_min_y, world_max_x, world_max_y