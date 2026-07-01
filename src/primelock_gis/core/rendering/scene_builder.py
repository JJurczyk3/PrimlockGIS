"""Create drawable objects from GIS data."""

from primelock_gis.core.models.contour import ContourPolyline, ContourSegment
from primelock_gis.core.models.vector import SpecialPoint, TopologyModel
from primelock_gis.core.rendering.scene import (
    DrawableTerrain,
    DrawablePoint,
    DrawablePolyline,
    DrawableText,
    Scene,
)
from primelock_gis.core.geometry import Point
from primelock_gis.core.rendering.symbology import (
    PointStyle,
    PolylineStyle,
    FillStyle,
    TextStyle,
    TerrainStyle,
)
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel


def terrain_to_scene(grid_model: GridModel, style: TerrainStyle | None = None) -> Scene:
    """Convert a grid model to a terrain colour scene layer."""
    if style is None:
        style = TerrainStyle()

    return Scene(
        terrains=[
            DrawableTerrain(
                grid=grid_model,
                style=style,
            )
        ]
    )


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
    vertex_by_id = tin_model.vertex_by_id()

    for edge in sorted(tin_model.unique_edge_keys()):
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


def contour_segments_to_scene(
    segments: list[ContourSegment],
    style: PolylineStyle | None = None,
) -> Scene:
    """Convert raw contour segments to display scene polylines."""
    if style is None:
        style = PolylineStyle(char="=")

    scene = Scene()

    for segment in segments:
        drawable = DrawablePolyline(
            points=[
                segment.start,
                segment.end,
            ],
            style=style,
        )
        scene.polylines.append(drawable)

    return scene


def contour_polylines_to_scene(
    polylines: list[ContourPolyline],
    style: PolylineStyle | None = None,
) -> Scene:
    """Convert traced contour polylines to display scene polylines."""
    if style is None:
        style = PolylineStyle(char="=")

    scene = Scene()

    for polyline in polylines:
        points = list(polyline.points)

        if (
            polyline.closed
            and len(points) >= 2
            and points[0] != points[-1]
        ):
            points.append(points[0])

        drawable = DrawablePolyline(
            points=points,
            style=style,
        )
        scene.polylines.append(drawable)

    return scene


def contours_to_scene(
    polylines: list[ContourPolyline],
    style: PolylineStyle | None = None,
) -> Scene:
    """Compatibility wrapper for traced contour polyline rendering."""
    return contour_polylines_to_scene(polylines, style)


def contour_labels_to_scene(
    polylines: list[ContourPolyline],
    style: TextStyle | None = None,
) -> Scene:
    """Convert contour levels to text labels placed on each polyline."""
    if style is None:
        style = TextStyle(color="#BAE6FD")

    scene = Scene()

    for polyline in polylines:
        if not polyline.points:
            continue

        label_point = polyline.points[len(polyline.points) // 2]
        scene.texts.append(
            DrawableText(
                position=label_point,
                text=f"{polyline.level:g}",
                style=style,
            )
        )

    return scene


def topology_to_scene(
    topology: TopologyModel,
    arc_style: PolylineStyle | None = None,
    node_style: PointStyle | None = None,
) -> Scene:
    """Convert topology nodes and arcs to a display scene."""
    if arc_style is None:
        arc_style = PolylineStyle(char="-")

    if node_style is None:
        node_style = PointStyle(char="o")

    scene = Scene()
    node_by_id = {
        node.id: node
        for node in topology.nodes
    }

    for arc in topology.arcs:
        start_node = node_by_id[arc.start_node]
        end_node = node_by_id[arc.end_node]
        points = [Point(start_node.x, start_node.y)]

        for x, y in arc.intermediate_points:
            points.append(Point(x, y))

        points.append(Point(end_node.x, end_node.y))
        scene.polylines.append(
            DrawablePolyline(
                points=points,
                style=arc_style,
            )
        )

    for node in topology.nodes:
        scene.points.append(
            DrawablePoint(
                position=Point(node.x, node.y),
                style=node_style,
            )
        )

    return scene
