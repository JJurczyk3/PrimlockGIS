"""Create drawable objects from GIS data."""

from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.rendering.scene import DrawablePoint, Scene
from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.symbology import PointStyle


def points_to_scene(points: list[SpecialPoint], style: PointStyle | None = None) -> Scene:
    """Convert the GIS coordinates to points on the screen."""
    if style is None:
        style = PointStyle()

    scene = Scene()

    for point in points:
        drawable = DrawablePoint(
            position=Point(point.x, point.y),
            style=style,
        )
        scene.points.append(drawable)
    return scene


def contours_to_scene():
    pass

def tin_to_scene():
    pass

def grid_to_scene():
    pass

def topology_to_scene():
    pass