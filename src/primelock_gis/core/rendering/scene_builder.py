"""Create drawable objects from GIS data."""

from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.rendering.scene import DrawablePoint, DrawablePolyline, Scene
from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.symbology import PointStyle, PolylineStyle, FillStyle
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel


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


def grid_to_scene(grid_model: GridModel, style=None) -> Scene:
    """Convert grid model to display scene."""
    if style is None:
        style = PolylineStyle()

    scene = Scene()

    # Vertical grid lines: fixed x, y from min to max.
    for col in range(grid_model.x_divisions + 1):
        x = grid_model.node_x(col)

        drawable = DrawablePolyline(
            points=[
                Point(x, grid_model.y_min),
                Point(x, grid_model.y_max),
            ],
            style=style,
        )
        scene.polylines.append(drawable)

    # Horizontal grid lines: fixed y, x from min to max.
    for row in range(grid_model.y_divisions + 1):
        y = grid_model.node_y(row)

        drawable = DrawablePolyline(
            points=[
                Point(grid_model.x_min, y),
                Point(grid_model.x_max, y),
            ],
            style=style,
        )
        scene.polylines.append(drawable)
    return scene


def tin_to_scene(tin_model: TinModel, style: PolylineStyle | None = None) -> Scene:
    """Convert TIN model to display scene."""
    if style is None:
        style = PolylineStyle(char="*")

    scene = Scene()
    vertex_by_id = {}

    for vertex in tin_model.vertices:
        vertex_by_id[vertex.id] = vertex

    drawn_edges = set()

    for triangle in tin_model.triangles:
        a_id, b_id, c_id = triangle.vertex_ids

        edges = [
            tuple(sorted((a_id, b_id))),
            tuple(sorted((b_id, c_id))),
            tuple(sorted((c_id, a_id))),
        ]
        for edge in edges:
            if edge in drawn_edges:
                continue
            drawn_edges.add(edge)

            start_vertex = vertex_by_id[edge[0]]
            end_vertex = vertex_by_id[edge[1]]

            drawable = DrawablePolyline(
                points=[
                    Point(start_vertex.x, start_vertex.y),
                    Point(end_vertex.x, end_vertex.y),
                ],
                style=style,
            )
            scene.polylines.append(drawable)
    return scene


def contours_to_scene():
    pass

def topology_to_scene():
    pass