"""Grid-based contour generation and tracing algorithms."""

import math
from collections.abc import Hashable

from primelock_gis.core.geometry import Point
from primelock_gis.core.models.contour import (
    ContourPolyline,
    ContourSegment,
    GridEdgeKey,
)
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinEdgeKey, TinModel, TinTriangle


EPS = 1e-9


def grid_value_range(grid: GridModel) -> tuple[float, float]:
    """Return the minimum and maximum z values in a grid model."""
    values = [value for row in grid.node_values for value in row]
    return min(values), max(values)


def tin_value_range(tin: TinModel) -> tuple[float, float]:
    """Return the minimum and maximum z values in a TIN model."""
    values = [vertex.z for vertex in tin.vertices]
    return min(values), max(values)


def generate_contour_levels(
    min_value: float,
    max_value: float,
    interval: float,
) -> list[float]:
    """Generate contour levels as interval multiples inside a value range."""
    if interval <= 0:
        raise ValueError("Contour interval must be positive")

    low = min(min_value, max_value)
    high = max(min_value, max_value)
    first_index = math.ceil((low + EPS) / interval)

    levels = []
    index = first_index

    while True:
        level = index * interval
        if level >= high - EPS:
            break

        if level > low + EPS:
            levels.append(_clean_float(level))

        index += 1

    return levels


def adjust_level_singularity(
    z: float,
    level: float,
    interval: float,
    eps: float = EPS,
) -> float:
    """Move values lying exactly on a contour level by a tiny amount."""
    if abs(z - level) <= eps:
        return z + interval / 5000.0

    return z


def edge_crosses_level(z1: float, z2: float, level: float) -> bool:
    """Return True when two edge endpoint values straddle a contour level."""
    return (z1 < level and z2 > level) or (z1 > level and z2 < level)


def interpolate_edge_crossing(
    p1: Point,
    z1: float,
    p2: Point,
    z2: float,
    level: float,
) -> Point:
    """Linearly interpolate the contour crossing point on a grid edge."""
    if abs(z2 - z1) <= EPS:
        raise ValueError("Cannot interpolate contour crossing on a flat edge")

    t = (level - z1) / (z2 - z1)
    x = p1.x + t * (p2.x - p1.x)
    y = p1.y + t * (p2.y - p1.y)
    return Point(x, y)


def contour_segments_for_cell(
    grid: GridModel,
    row: int,
    col: int,
    level: float,
    interval: float,
) -> list[ContourSegment]:
    """Generate raw contour segments for one grid cell."""
    p00 = _grid_node_point(grid, row, col)
    p10 = _grid_node_point(grid, row, col + 1)
    p11 = _grid_node_point(grid, row + 1, col + 1)
    p01 = _grid_node_point(grid, row + 1, col)

    z00 = grid.node_value(row, col)
    z10 = grid.node_value(row, col + 1)
    z11 = grid.node_value(row + 1, col + 1)
    z01 = grid.node_value(row + 1, col)

    edge_specs = [
        (
            "bottom",
            GridEdgeKey("horizontal", row, col),
            p00,
            z00,
            p10,
            z10,
        ),
        (
            "right",
            GridEdgeKey("vertical", row, col + 1),
            p10,
            z10,
            p11,
            z11,
        ),
        (
            "top",
            GridEdgeKey("horizontal", row + 1, col),
            p01,
            z01,
            p11,
            z11,
        ),
        (
            "left",
            GridEdgeKey("vertical", row, col),
            p00,
            z00,
            p01,
            z01,
        ),
    ]

    crossings = []
    crossing_by_name = {}

    for name, edge_key, p1, z1, p2, z2 in edge_specs:
        adjusted_z1 = adjust_level_singularity(z1, level, interval)
        adjusted_z2 = adjust_level_singularity(z2, level, interval)

        if not edge_crosses_level(adjusted_z1, adjusted_z2, level):
            continue

        crossing_point = interpolate_edge_crossing(
            p1,
            adjusted_z1,
            p2,
            adjusted_z2,
            level,
        )
        crossing = (name, edge_key, crossing_point)
        crossings.append(crossing)
        crossing_by_name[name] = crossing

    if len(crossings) == 0:
        return []

    if len(crossings) == 2:
        return [_segment_from_crossings(level, crossings[0], crossings[1])]

    if len(crossings) == 4:
        center_z = (z00 + z10 + z11 + z01) / 4

        if center_z >= level:
            pairs = [
                ("bottom", "left"),
                ("right", "top"),
            ]
        else:
            pairs = [
                ("bottom", "right"),
                ("top", "left"),
            ]

        return [
            _segment_from_crossings(
                level,
                crossing_by_name[start_name],
                crossing_by_name[end_name],
            )
            for start_name, end_name in pairs
        ]

    # After singularity adjustment a regular square cell should have 0, 2, or
    # 4 crossings. Other counts indicate a degenerate flat-edge case, so this
    # first implementation leaves the cell untraced rather than inventing
    # unstable topology.
    return []


def contour_segments_from_grid(
    grid: GridModel,
    levels: list[float],
    interval: float,
) -> list[ContourSegment]:
    """Generate raw contour segments for all cells and levels in a grid."""
    segments = []

    for level in levels:
        for row in range(grid.y_divisions):
            for col in range(grid.x_divisions):
                segments.extend(
                    contour_segments_for_cell(
                        grid,
                        row,
                        col,
                        level,
                        interval,
                    )
                )

    return segments


def contour_segments_for_triangle(
    tin: TinModel,
    triangle: TinTriangle,
    level: float,
    interval: float,
) -> list[ContourSegment]:
    """Generate raw contour segments for one TIN triangle."""
    vertex_by_id = tin.vertex_by_id()
    crossings: list[tuple[TinEdgeKey, Point]] = []

    for edge_index in range(3):
        start_vertex_id, end_vertex_id = triangle.edge_vertex_ids(edge_index)
        start_vertex = vertex_by_id[start_vertex_id]
        end_vertex = vertex_by_id[end_vertex_id]
        adjusted_start_z = adjust_level_singularity(
            start_vertex.z,
            level,
            interval,
        )
        adjusted_end_z = adjust_level_singularity(
            end_vertex.z,
            level,
            interval,
        )

        if not edge_crosses_level(adjusted_start_z, adjusted_end_z, level):
            continue

        crossing_point = interpolate_edge_crossing(
            Point(start_vertex.x, start_vertex.y),
            adjusted_start_z,
            Point(end_vertex.x, end_vertex.y),
            adjusted_end_z,
            level,
        )
        crossings.append((triangle.edge_key(edge_index), crossing_point))

    if len(crossings) != 2:
        return []

    start_edge, start_point = crossings[0]
    end_edge, end_point = crossings[1]
    return [
        ContourSegment(
            level=level,
            start=start_point,
            end=end_point,
            start_edge=start_edge,
            end_edge=end_edge,
        )
    ]


def contour_segments_from_tin(
    tin: TinModel,
    levels: list[float],
    interval: float,
) -> list[ContourSegment]:
    """Generate raw contour segments for all triangles and levels in a TIN."""
    segments = []

    for level in levels:
        for triangle in tin.triangles:
            segments.extend(
                contour_segments_for_triangle(
                    tin,
                    triangle,
                    level,
                    interval,
                )
            )

    return segments


def contour_polylines_from_tin(
    tin: TinModel,
    levels: list[float],
    interval: float,
) -> list[ContourPolyline]:
    """Generate and trace TIN contours into ordered contour polylines."""
    segments = contour_segments_from_tin(tin, levels, interval)
    return trace_tin_contour_segments(segments, tin)


def trace_contour_segments(
    segments: list[ContourSegment],
    grid: GridModel,
) -> list[ContourPolyline]:
    """Trace raw contour segments into ordered open and closed polylines."""
    adjacency = _build_segment_adjacency(segments)
    used_segments: set[int] = set()
    polylines = []

    for segment_index, segment in enumerate(segments):
        if segment_index in used_segments:
            continue

        boundary_edges = [
            edge
            for edge in (segment.start_edge, segment.end_edge)
            if is_boundary_edge(edge, grid)
        ]
        if not boundary_edges:
            continue

        polylines.append(
            _trace_from_segment(
                start_segment_index=segment_index,
                start_edge=boundary_edges[0],
                segments=segments,
                adjacency=adjacency,
                used_segments=used_segments,
                grid=grid,
                trace_closed=False,
            )
        )

    for segment_index, segment in enumerate(segments):
        if segment_index in used_segments:
            continue

        polylines.append(
            _trace_from_segment(
                start_segment_index=segment_index,
                start_edge=segment.start_edge,
                segments=segments,
                adjacency=adjacency,
                used_segments=used_segments,
                grid=grid,
                trace_closed=True,
            )
        )

    return polylines


def trace_tin_contour_segments(
    segments: list[ContourSegment],
    tin: TinModel,
) -> list[ContourPolyline]:
    """Trace raw TIN contour segments into ordered open and closed polylines."""
    boundary_edges = _tin_boundary_edges(tin)
    adjacency = _build_segment_adjacency(segments)
    used_segments: set[int] = set()
    polylines = []

    for segment_index, segment in enumerate(segments):
        if segment_index in used_segments:
            continue

        segment_boundary_edges = [
            edge
            for edge in (segment.start_edge, segment.end_edge)
            if edge in boundary_edges
        ]
        if not segment_boundary_edges:
            continue

        polylines.append(
            _trace_tin_from_segment(
                start_segment_index=segment_index,
                start_edge=segment_boundary_edges[0],
                segments=segments,
                adjacency=adjacency,
                used_segments=used_segments,
                boundary_edges=boundary_edges,
                trace_closed=False,
            )
        )

    for segment_index, segment in enumerate(segments):
        if segment_index in used_segments:
            continue

        polylines.append(
            _trace_tin_from_segment(
                start_segment_index=segment_index,
                start_edge=segment.start_edge,
                segments=segments,
                adjacency=adjacency,
                used_segments=used_segments,
                boundary_edges=boundary_edges,
                trace_closed=True,
            )
        )

    return polylines


def is_boundary_edge(edge: GridEdgeKey, grid: GridModel) -> bool:
    """Return True when a grid edge lies on the outer grid boundary."""
    if edge.kind == "horizontal":
        return edge.row == 0 or edge.row == grid.y_divisions

    return edge.col == 0 or edge.col == grid.x_divisions


def _grid_node_point(grid: GridModel, row: int, col: int) -> Point:
    return Point(grid.node_x(col), grid.node_y(row))


def _segment_from_crossings(level: float, start, end) -> ContourSegment:
    _, start_edge, start_point = start
    _, end_edge, end_point = end

    return ContourSegment(
        level=level,
        start=start_point,
        end=end_point,
        start_edge=start_edge,
        end_edge=end_edge,
    )


def _build_segment_adjacency(
    segments: list[ContourSegment],
) -> dict[Hashable, list[int]]:
    adjacency: dict[Hashable, list[int]] = {}

    for index, segment in enumerate(segments):
        adjacency.setdefault(segment.start_edge, []).append(index)
        adjacency.setdefault(segment.end_edge, []).append(index)

    for connected_segments in adjacency.values():
        connected_segments.sort()

    return adjacency


def _trace_from_segment(
    start_segment_index: int,
    start_edge: Hashable,
    segments: list[ContourSegment],
    adjacency: dict[Hashable, list[int]],
    used_segments: set[int],
    grid: GridModel,
    trace_closed: bool,
) -> ContourPolyline:
    start_segment = segments[start_segment_index]
    level = start_segment.level
    current_segment_index = start_segment_index
    current_edge = start_edge
    points = []
    closed = False

    while True:
        segment = segments[current_segment_index]
        start_point, end_point, next_edge = _orient_segment(segment, current_edge)

        if not points:
            points.append(start_point)

        points.append(end_point)
        used_segments.add(current_segment_index)

        if trace_closed and next_edge == start_edge:
            closed = True
            break

        if not trace_closed and is_boundary_edge(next_edge, grid):
            break

        next_segment_index = _choose_continuation(
            edge=next_edge,
            level=level,
            adjacency=adjacency,
            segments=segments,
            used_segments=used_segments,
        )

        if next_segment_index is None:
            break

        current_segment_index = next_segment_index
        current_edge = next_edge

    return ContourPolyline(
        level=level,
        points=points,
        closed=closed,
    )


def _trace_tin_from_segment(
    start_segment_index: int,
    start_edge: Hashable,
    segments: list[ContourSegment],
    adjacency: dict[Hashable, list[int]],
    used_segments: set[int],
    boundary_edges: set[TinEdgeKey],
    trace_closed: bool,
) -> ContourPolyline:
    start_segment = segments[start_segment_index]
    level = start_segment.level
    current_segment_index = start_segment_index
    current_edge = start_edge
    points = []
    closed = False

    while True:
        segment = segments[current_segment_index]
        start_point, end_point, next_edge = _orient_segment(segment, current_edge)

        if not points:
            points.append(start_point)

        points.append(end_point)
        used_segments.add(current_segment_index)

        if trace_closed and next_edge == start_edge:
            closed = True
            break

        if not trace_closed and next_edge in boundary_edges:
            break

        next_segment_index = _choose_continuation(
            edge=next_edge,
            level=level,
            adjacency=adjacency,
            segments=segments,
            used_segments=used_segments,
        )

        if next_segment_index is None:
            break

        current_segment_index = next_segment_index
        current_edge = next_edge

    return ContourPolyline(
        level=level,
        points=points,
        closed=closed,
    )


def _orient_segment(
    segment: ContourSegment,
    current_edge: Hashable,
) -> tuple[Point, Point, Hashable]:
    if segment.start_edge == current_edge:
        return segment.start, segment.end, segment.end_edge

    if segment.end_edge == current_edge:
        return segment.end, segment.start, segment.start_edge

    raise ValueError("Current edge is not connected to contour segment")


def _choose_continuation(
    edge: Hashable,
    level: float,
    adjacency: dict[Hashable, list[int]],
    segments: list[ContourSegment],
    used_segments: set[int],
) -> int | None:
    candidates = []

    for segment_index in adjacency.get(edge, []):
        if segment_index in used_segments:
            continue

        if segments[segment_index].level != level:
            continue

        candidates.append(segment_index)

    if not candidates:
        return None

    return min(candidates)


def _tin_boundary_edges(tin: TinModel) -> set[TinEdgeKey]:
    edge_counts: dict[TinEdgeKey, int] = {}

    for triangle in tin.triangles:
        for edge_index in range(3):
            edge = triangle.edge_key(edge_index)
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    return {
        edge
        for edge, count in edge_counts.items()
        if count == 1
    }


def _clean_float(value: float) -> float:
    rounded = round(value, 10)

    if abs(rounded - round(rounded)) <= EPS:
        return float(round(rounded))

    return rounded
