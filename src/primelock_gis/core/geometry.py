"""Shared geometry utilities."""

from dataclasses import dataclass
from math import hypot
from typing import Literal, Protocol

EPS = 1e-9


class Coordinate2D(Protocol):
    """Structural type for objects with x/y coordinates."""

    x: float
    y: float


IntersectionKind = Literal["none", "touch", "intersect", "overlap"]


@dataclass(frozen=True)
class Point:
    """An immutable 2D coordinate."""

    x: float
    y: float


@dataclass(frozen=True)
class Box:
    """An axis-aligned 2D bounding box."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class SegmentIntersection:
    """The classified result of a segment-intersection test."""

    kind: IntersectionKind
    point: Point | None = None


def almost_equal(a: float, b: float, eps: float = EPS) -> bool:
    """Return True when two numeric values are within tolerance."""
    return abs(a - b) <= eps


def distance(p: Coordinate2D, q: Coordinate2D) -> float:
    """Return Euclidean distance between two points."""
    return hypot(p.x - q.x, p.y - q.y)


def cross(a: Coordinate2D, b: Coordinate2D, c: Coordinate2D) -> float:
    """Return the 2D cross product of vectors AB and AC."""
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def orientation(
    a: Coordinate2D,
    b: Coordinate2D,
    c: Coordinate2D,
    eps: float = EPS,
) -> int:
    """Classify the turn formed by points a, b, and c."""
    cross_product = cross(a, b, c)

    if almost_equal(cross_product, 0, eps):
        return 0

    return 1 if cross_product > 0 else -1


def bbox_from_points(a: Coordinate2D, b: Coordinate2D) -> Box:
    """Return the bounding box of a two-point segment."""
    return Box(
        min_x=min(a.x, b.x),
        min_y=min(a.y, b.y),
        max_x=max(a.x, b.x),
        max_y=max(a.y, b.y),
    )


def bbox_intersects(box1: Box, box2: Box, eps: float = EPS) -> bool:
    """Return True when two bounding boxes overlap or touch."""
    return not (
        box1.max_x < box2.min_x - eps
        or box2.max_x < box1.min_x - eps
        or box1.max_y < box2.min_y - eps
        or box2.max_y < box1.min_y - eps
    )


def point_on_segment(
    p: Coordinate2D,
    a: Coordinate2D,
    b: Coordinate2D,
    eps: float = EPS,
) -> bool:
    """Return True when point p lies on segment ab."""
    if orientation(a, b, p, eps) != 0:
        return False

    return (
        min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps
    )


def segment_intersects(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
    eps: float = EPS,
) -> SegmentIntersection:
    """Classify the intersection between segments ab and cd."""
    if not bbox_intersects(bbox_from_points(a, b), bbox_from_points(c, d), eps):
        return SegmentIntersection("none")

    r_x = b.x - a.x
    r_y = b.y - a.y
    s_x = d.x - c.x
    s_y = d.y - c.y

    denominator = r_x * s_y - r_y * s_x
    c_minus_a_x = c.x - a.x
    c_minus_a_y = c.y - a.y

    if almost_equal(denominator, 0, eps):
        if not almost_equal(cross(a, b, c), 0, eps):
            return SegmentIntersection("none")
        return _collinear_segment_intersection(a, b, c, d, eps)

    t = (c_minus_a_x * s_y - c_minus_a_y * s_x) / denominator
    u = (c_minus_a_x * r_y - c_minus_a_y * r_x) / denominator

    if not (-eps <= t <= 1 + eps and -eps <= u <= 1 + eps):
        return SegmentIntersection("none")

    intersection_point = Point(
        x=a.x + t * r_x,
        y=a.y + t * r_y,
    )
    if (
        distance(intersection_point, a) <= eps
        or distance(intersection_point, b) <= eps
        or distance(intersection_point, c) <= eps
        or distance(intersection_point, d) <= eps
    ):
        return SegmentIntersection("touch", intersection_point)

    return SegmentIntersection("intersect", intersection_point)


def _collinear_segment_intersection(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
    eps: float,
) -> SegmentIntersection:
    overlap_points = [point for point in (a, b) if point_on_segment(point, c, d, eps)]
    overlap_points.extend(
        point for point in (c, d) if point_on_segment(point, a, b, eps)
    )

    unique_points: list[Point] = []
    for point in overlap_points:
        if not any(distance(point, existing) <= eps for existing in unique_points):
            unique_points.append(point)

    if not unique_points:
        return SegmentIntersection("none")
    if len(unique_points) == 1:
        return SegmentIntersection("touch", unique_points[0])
    return SegmentIntersection("overlap")


def polygon_signed_area(points: list[Point]) -> float:
    """Return signed polygon area; sign indicates ring orientation."""
    if len(points) < 3:
        return 0.0

    total = 0.0

    for i in range(len(points)):
        current = points[i]
        next_point = points[(i + 1) % len(points)]

        total += current.x * next_point.y
        total -= current.y * next_point.x
    return total / 2


def distance_squared(a: Coordinate2D, b: Coordinate2D) -> float:
    """Return squared Euclidean distance without taking a square root."""
    dx = a.x - b.x
    dy = a.y - b.y
    return dx * dx + dy * dy


def circumcircle_contains(
    a: Coordinate2D,
    b: Coordinate2D,
    c: Coordinate2D,
    p: Coordinate2D,
    eps: float = EPS,
) -> bool:
    """Return True when point p lies inside triangle abc's circumcircle."""
    ax = a.x - p.x
    ay = a.y - p.y
    bx = b.x - p.x
    by = b.y - p.y
    cx = c.x - p.x
    cy = c.y - p.y

    determinant = (
        (ax * ax + ay * ay) * (bx * cy - by * cx)
        - (bx * bx + by * by) * (ax * cy - ay * cx)
        + (cx * cx + cy * cy) * (ax * by - ay * bx)
    )

    triangle_orientation = orientation(a, b, c, eps)

    if triangle_orientation > 0:
        return determinant > eps

    if triangle_orientation < 0:
        return determinant < -eps

    return False
