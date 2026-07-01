import pytest

from primelock_gis.core.algorithms.contour import (
    adjust_level_singularity,
    contour_segments_for_cell,
    contour_segments_from_grid,
    contour_segments_from_tin,
    edge_crosses_level,
    generate_contour_levels,
    grid_value_range,
    interpolate_edge_crossing,
    tin_value_range,
    trace_contour_segments,
    trace_tin_contour_segments,
)
from primelock_gis.core.geometry import Point
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel, TinTriangle, TinVertex
from primelock_gis.core.rendering.scene_builder import (
    contour_labels_to_scene,
    contour_polylines_to_scene,
)


def make_grid(node_values: list[list[float]]) -> GridModel:
    y_divisions = len(node_values) - 1
    x_divisions = len(node_values[0]) - 1

    return GridModel(
        x_min=0.0,
        y_min=0.0,
        x_max=x_divisions * 10.0,
        y_max=y_divisions * 10.0,
        x_divisions=x_divisions,
        y_divisions=y_divisions,
        node_values=node_values,
    )


def assert_point(point: Point, x: float, y: float) -> None:
    assert point.x == pytest.approx(x)
    assert point.y == pytest.approx(y)


def test_grid_value_range_returns_minimum_and_maximum_z_values():
    grid = make_grid([
        [0.0, 10.0],
        [-5.0, 20.0],
    ])

    assert grid_value_range(grid) == (-5.0, 20.0)


def test_generate_contour_levels_inside_negative_range():
    levels = generate_contour_levels(
        min_value=-431,
        max_value=-122,
        interval=50,
    )

    assert levels == [-400, -350, -300, -250, -200, -150]


def test_generate_contour_levels_requires_positive_interval():
    with pytest.raises(ValueError):
        generate_contour_levels(0, 10, 0)


def test_edge_crosses_level_uses_strict_opposite_side_logic():
    assert edge_crosses_level(0, 10, 5) is True
    assert edge_crosses_level(0, 4, 5) is False
    assert edge_crosses_level(10, 0, 5) is True
    assert edge_crosses_level(5, 10, 5) is False


def test_interpolate_edge_crossing_midpoint():
    point = interpolate_edge_crossing(
        p1=Point(0, 0),
        z1=0,
        p2=Point(10, 0),
        z2=10,
        level=5,
    )

    assert_point(point, 5, 0)


def test_interpolate_edge_crossing_rejects_flat_edge():
    with pytest.raises(ValueError):
        interpolate_edge_crossing(Point(0, 0), 5, Point(10, 0), 5, 5)


def test_one_cell_vertical_contour_segment():
    grid = make_grid([
        [0.0, 10.0],
        [0.0, 10.0],
    ])

    segments = contour_segments_for_cell(grid, row=0, col=0, level=5, interval=5)

    assert len(segments) == 1
    assert_point(segments[0].start, 5, 0)
    assert_point(segments[0].end, 5, 10)


def test_one_cell_horizontal_contour_segment():
    grid = make_grid([
        [0.0, 0.0],
        [10.0, 10.0],
    ])

    segments = contour_segments_for_cell(grid, row=0, col=0, level=5, interval=5)

    assert len(segments) == 1
    assert_point(segments[0].start, 10, 5)
    assert_point(segments[0].end, 0, 5)


def test_singularity_adjustment_moves_exact_level_slightly_up():
    assert adjust_level_singularity(5.0, level=5.0, interval=10.0) == pytest.approx(
        5.002
    )


def test_cell_with_exact_level_corner_does_not_crash_or_duplicate_segments():
    grid = make_grid([
        [5.0, 10.0],
        [0.0, 10.0],
    ])

    segments = contour_segments_for_cell(grid, row=0, col=0, level=5, interval=10)

    assert len(segments) == 1


def test_open_contour_trace_crosses_boundary_to_boundary():
    grid = make_grid([
        [0.0, 10.0],
        [0.0, 10.0],
        [0.0, 10.0],
    ])
    segments = contour_segments_from_grid(grid, levels=[5], interval=5)

    polylines = trace_contour_segments(segments, grid)

    assert len(polylines) == 1
    assert polylines[0].closed is False
    assert len(polylines[0].points) == 3
    assert_point(polylines[0].points[0], 5, 0)
    assert_point(polylines[0].points[-1], 5, 20)


def test_closed_contour_trace_around_center_island():
    grid = make_grid([
        [0.0, 0.0, 0.0],
        [0.0, 10.0, 0.0],
        [0.0, 0.0, 0.0],
    ])
    segments = contour_segments_from_grid(grid, levels=[5], interval=5)

    polylines = trace_contour_segments(segments, grid)

    assert len(polylines) == 1
    assert polylines[0].closed is True
    assert len(polylines[0].points) == 5


def test_contour_polylines_to_scene_creates_drawable_polylines():
    grid = make_grid([
        [0.0, 10.0],
        [0.0, 10.0],
    ])
    segments = contour_segments_from_grid(grid, levels=[5], interval=5)
    polylines = trace_contour_segments(segments, grid)

    scene = contour_polylines_to_scene(polylines)

    assert len(scene.polylines) == 1
    assert scene.polylines[0].points == polylines[0].points


def test_tin_value_range_returns_minimum_and_maximum_z_values():
    tin = TinModel(
        vertices=[
            TinVertex(0, 0, 0, -10),
            TinVertex(1, 10, 0, 5),
            TinVertex(2, 0, 10, 20),
        ],
        triangles=[TinTriangle(0, (0, 1, 2))],
    )

    assert tin_value_range(tin) == (-10, 20)


def test_one_triangle_tin_contour_segment():
    tin = TinModel(
        vertices=[
            TinVertex(0, 0, 0, 0),
            TinVertex(1, 10, 0, 10),
            TinVertex(2, 0, 10, 0),
        ],
        triangles=[TinTriangle(0, (0, 1, 2))],
    )

    segments = contour_segments_from_tin(tin, levels=[5], interval=5)

    assert len(segments) == 1
    assert_point(segments[0].start, 5, 0)
    assert_point(segments[0].end, 5, 5)


def test_tin_contour_trace_can_return_open_boundary_polyline():
    tin = TinModel(
        vertices=[
            TinVertex(0, 0, 0, 0),
            TinVertex(1, 10, 0, 10),
            TinVertex(2, 0, 10, 0),
        ],
        triangles=[TinTriangle(0, (0, 1, 2))],
    )
    segments = contour_segments_from_tin(tin, levels=[5], interval=5)

    polylines = trace_tin_contour_segments(segments, tin)

    assert len(polylines) == 1
    assert polylines[0].closed is False
    assert len(polylines[0].points) == 2


def test_contour_labels_to_scene_creates_level_text_labels():
    grid = make_grid([
        [0.0, 10.0],
        [0.0, 10.0],
    ])
    segments = contour_segments_from_grid(grid, levels=[5], interval=5)
    polylines = trace_contour_segments(segments, grid)

    scene = contour_labels_to_scene(polylines)

    assert len(scene.texts) == 1
    assert scene.texts[0].text == "5"
