"""Build simple node/arc/polygon topology from linework."""

from dataclasses import dataclass

from primelock_gis.core.geometry import (
    EPS,
    Point,
    distance,
    polygon_signed_area,
    segment_intersects,
)
from primelock_gis.core.models.contour import ContourPolyline
from primelock_gis.core.models.vector import Arc, Node, Polygon, TopologyModel


@dataclass
class _PolylineInput:
    points: list[Point]
    closed: bool


@dataclass(frozen=True)
class _SegmentInput:
    polyline_index: int
    start: Point
    end: Point


def build_topology_from_contour_polylines(
    polylines: list[ContourPolyline],
    tolerance: float = EPS,
) -> TopologyModel:
    """Build topology from traced contour polylines."""
    return build_topology_from_point_sequences(
        [polyline.points for polyline in polylines],
        closed_flags=[polyline.closed for polyline in polylines],
        tolerance=tolerance,
    )


def build_topology_from_point_sequences(
    point_sequences: list[list[Point]],
    closed_flags: list[bool] | None = None,
    tolerance: float = EPS,
) -> TopologyModel:
    """Build node/arc/polygon topology from point sequences.

    Nodes are created at vertices and detected intersections. Collinear overlaps
    remain duplicate linework in this first topology pass.
    """
    if tolerance <= 0:
        raise ValueError("Topology tolerance must be positive")

    polylines = _prepare_polyline_inputs(point_sequences, closed_flags, tolerance)
    segments = _build_segments(polylines, tolerance)
    split_points_by_segment = _initial_split_points(segments)

    _add_intersection_split_points(
        segments,
        split_points_by_segment,
        tolerance,
    )

    nodes, arcs, arc_ids_by_polyline = _build_topology_arcs(
        polylines,
        segments,
        split_points_by_segment,
        tolerance,
    )
    polygons = _build_polygon_candidates(
        polylines,
        arcs,
        arc_ids_by_polyline,
        tolerance,
    )

    return TopologyModel(
        nodes=nodes,
        arcs=arcs,
        polygons=polygons,
    )


def _build_topology_arcs(
    polylines: list[_PolylineInput],
    segments: list[_SegmentInput],
    split_points_by_segment: dict[int, list[Point]],
    tolerance: float,
) -> tuple[list[Node], list[Arc], list[list[int]]]:
    """Create nodes and arcs from split line segments."""
    nodes: list[Node] = []
    arcs: list[Arc] = []
    arc_ids_by_polyline: list[list[int]] = [[] for _ in polylines]

    for segment_index, segment in enumerate(segments):
        split_points = _sorted_segment_split_points(
            segment,
            split_points_by_segment[segment_index],
            tolerance,
        )

        for start, end in zip(split_points, split_points[1:]):
            if distance(start, end) <= tolerance:
                continue

            start_node_id = _get_or_create_node(nodes, start, tolerance)
            end_node_id = _get_or_create_node(nodes, end, tolerance)
            arc = Arc(
                id=len(arcs),
                start_node=start_node_id,
                end_node=end_node_id,
            )
            arcs.append(arc)
            arc_ids_by_polyline[segment.polyline_index].append(arc.id)
            _attach_arc_to_node(nodes[start_node_id], arc.id)
            _attach_arc_to_node(nodes[end_node_id], arc.id)

    return nodes, arcs, arc_ids_by_polyline


def _prepare_polyline_inputs(
    point_sequences: list[list[Point]],
    closed_flags: list[bool] | None,
    tolerance: float,
) -> list[_PolylineInput]:
    if closed_flags is not None and len(closed_flags) != len(point_sequences):
        raise ValueError("closed_flags length must match point_sequences length")

    polylines = []

    for index, points in enumerate(point_sequences):
        closed = bool(closed_flags[index]) if closed_flags is not None else False
        prepared_points = _without_consecutive_duplicate_points(points, tolerance)

        if closed and prepared_points:
            first = prepared_points[0]
            last = prepared_points[-1]
            if distance(first, last) > tolerance:
                prepared_points.append(first)

        if len(prepared_points) >= 2:
            polylines.append(
                _PolylineInput(
                    points=prepared_points,
                    closed=closed,
                )
            )

    return polylines


def _without_consecutive_duplicate_points(
    points: list[Point],
    tolerance: float,
) -> list[Point]:
    prepared = []

    for point in points:
        if prepared and distance(prepared[-1], point) <= tolerance:
            continue

        prepared.append(point)

    return prepared


def _build_segments(
    polylines: list[_PolylineInput],
    tolerance: float,
) -> list[_SegmentInput]:
    segments = []

    for polyline_index, polyline in enumerate(polylines):
        for start, end in zip(polyline.points, polyline.points[1:]):
            if distance(start, end) <= tolerance:
                continue

            segments.append(
                _SegmentInput(
                    polyline_index=polyline_index,
                    start=start,
                    end=end,
                )
            )

    return segments


def _initial_split_points(
    segments: list[_SegmentInput],
) -> dict[int, list[Point]]:
    return {
        index: [segment.start, segment.end] for index, segment in enumerate(segments)
    }


def _add_intersection_split_points(
    segments: list[_SegmentInput],
    split_points_by_segment: dict[int, list[Point]],
    tolerance: float,
) -> None:
    for first_index in range(len(segments)):
        first = segments[first_index]

        for second_index in range(first_index + 1, len(segments)):
            second = segments[second_index]
            intersection = segment_intersects(
                first.start,
                first.end,
                second.start,
                second.end,
                eps=tolerance,
            )

            if intersection.kind not in ("touch", "intersect"):
                continue

            if intersection.point is None:
                continue

            _add_unique_point(
                split_points_by_segment[first_index],
                intersection.point,
                tolerance,
            )
            _add_unique_point(
                split_points_by_segment[second_index],
                intersection.point,
                tolerance,
            )


def _add_unique_point(
    points: list[Point],
    point: Point,
    tolerance: float,
) -> None:
    if any(distance(existing, point) <= tolerance for existing in points):
        return

    points.append(point)


def _sorted_segment_split_points(
    segment: _SegmentInput,
    points: list[Point],
    tolerance: float,
) -> list[Point]:
    unique_points = []

    for point in points:
        _add_unique_point(unique_points, point, tolerance)

    return sorted(
        unique_points,
        key=lambda point: _segment_parameter(segment, point),
    )


def _segment_parameter(segment: _SegmentInput, point: Point) -> float:
    dx = segment.end.x - segment.start.x
    dy = segment.end.y - segment.start.y
    length_squared = dx * dx + dy * dy

    if length_squared <= EPS:
        return 0.0

    return (
        (point.x - segment.start.x) * dx + (point.y - segment.start.y) * dy
    ) / length_squared


def _get_or_create_node(
    nodes: list[Node],
    point: Point,
    tolerance: float,
) -> int:
    for node in nodes:
        node_point = Point(node.x, node.y)
        if distance(node_point, point) <= tolerance:
            return node.id

    node_id = len(nodes)
    nodes.append(
        Node(
            id=node_id,
            x=point.x,
            y=point.y,
        )
    )
    return node_id


def _attach_arc_to_node(node: Node, arc_id: int) -> None:
    if arc_id not in node.arc_ids:
        node.arc_ids.append(arc_id)


def _build_polygon_candidates(
    polylines: list[_PolylineInput],
    arcs: list[Arc],
    arc_ids_by_polyline: list[list[int]],
    tolerance: float,
) -> list[Polygon]:
    polygons = []

    for polyline_index, polyline in enumerate(polylines):
        if not polyline.closed:
            continue

        polygon_points = _polygon_points_without_duplicate_close(
            polyline.points,
            tolerance,
        )
        if len(polygon_points) < 3:
            continue

        signed_area = polygon_signed_area(polygon_points)
        if abs(signed_area) <= tolerance:
            continue

        arc_ids = arc_ids_by_polyline[polyline_index]
        if not arc_ids:
            continue

        polygon = Polygon(
            id=len(polygons),
            arc_ids=list(arc_ids),
        )
        polygons.append(polygon)
        _assign_polygon_side_to_arcs(arcs, polygon, signed_area)

    return polygons


def _polygon_points_without_duplicate_close(
    points: list[Point],
    tolerance: float,
) -> list[Point]:
    polygon_points = list(points)

    if (
        len(polygon_points) >= 2
        and distance(polygon_points[0], polygon_points[-1]) <= tolerance
    ):
        polygon_points.pop()

    return polygon_points


def _assign_polygon_side_to_arcs(
    arcs: list[Arc],
    polygon: Polygon,
    signed_area: float,
) -> None:
    for arc_id in polygon.arc_ids:
        arc = arcs[arc_id]

        if signed_area > 0:
            arc.left_polygon = polygon.id
        else:
            arc.right_polygon = polygon.id
