"""Shared geometry utilities."""

from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Box:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class SegmentIntersection:
    kind: str
    point: Point | None = None


def almost_equal(a, b, eps=EPS):
    """Return True when two numeric values are within tolerance."""
    return abs(a - b) <= eps


def distance(p, q):
    """Return Euclidean distance between two points."""
    dx = p.x - q.x
    dy = p.y - q.y
    return (dx * dx + dy * dy) ** 0.5


def cross(a, b, c):
    """Return the 2D cross product of vectors AB and AC."""
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def orientation(a, b, c, eps=EPS):
    """Classify the turn formed by points a, b, and c."""
    cross_product = cross(a, b, c)

    if almost_equal(cross_product, 0, eps):
        return 0

    return 1 if cross_product > 0 else -1


def bbox_from_points(a, b):
    """Return the bounding box of a two-point segment."""
    return Box(
        min_x=min(a.x, b.x),
        min_y=min(a.y, b.y),
        max_x=max(a.x, b.x),
        max_y=max(a.y, b.y),
    )


def bbox_intersects(box1, box2, eps=EPS):
    """Return True when two bounding boxes overlap or touch."""
    return not (
        box1.max_x < box2.min_x - eps
        or box2.max_x < box1.min_x - eps
        or box1.max_y < box2.min_y - eps
        or box2.max_y < box1.min_y - eps
    )


def point_on_segment(p, a, b, eps=EPS):
    """Return True when point p lies on segment ab."""
    if orientation(a, b, p, eps) != 0:
        return False

    return (
        min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps
    )


def segment_intersects(a, b, c, d, eps=EPS):
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

    # Parallel case
    if almost_equal(denominator, 0, eps):
        # Parallel but not collinear
        if not almost_equal(cross(a, b, c), 0, eps):
            return SegmentIntersection("none")

        # Collinear: check shared endpoints
        overlap_points = []

        for p in (a, b):
            if point_on_segment(p, c, d, eps):
                overlap_points.append(p)

        for p in (c, d):
            if point_on_segment(p, a, b, eps):
                overlap_points.append(p)

        unique_points = []
        for p in overlap_points:
            if not any(distance(p, q) <= eps for q in unique_points):
                unique_points.append(p)

        if len(unique_points) == 0:
            return SegmentIntersection("none")

        if len(unique_points) == 1:
            return SegmentIntersection("touch", unique_points[0])

        return SegmentIntersection("overlap")

    # Non-parallel case
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


def distance_squared(a: Point, b: Point) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return dx * dx + dy * dy


def circumcircle_contains(a: Point, b: Point, c: Point, p: Point, eps: float = EPS) -> bool:
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
