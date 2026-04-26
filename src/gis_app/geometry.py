from dataclasses import dataclass
import math

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


# Return True if a and b are almost equal, False otherwise
def almost_equal(a, b, eps=EPS):
    return abs(a - b) <= eps


# Return the distance between points p and q
def distance(p, q):
    return math.hypot(p.x - q.x, p.y - q.y)


# Return the cross product of vectors AB and AC
def cross(a, b, c):
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


# Return what is the direction of the turn formed by points a, b, c
def orientation(a, b, c, eps=EPS):
    cross_product = cross(a, b, c)

    if almost_equal(cross_product, 0, eps):
        return 0  # Collinear

    return 1 if cross_product > 0 else -1  # Left turn or right turn


def bbox_from_points(a, b):
    return Box(
        min_x=min(a.x, b.x),
        min_y=min(a.y, b.y),
        max_x=max(a.x, b.x),
        max_y=max(a.y, b.y),
    )


# Return True if the bounding boxes of box1 and box2 intersect, False otherwise
def bbox_intersects(box1, box2, eps=EPS):
    return not (
        box1.max_x < box2.min_x - eps
        or box2.max_x < box1.min_x - eps
        or box1.max_y < box2.min_y - eps
        or box2.max_y < box1.min_y - eps
    )


# Return True if point p is on the line segment defined by points a and b, False otherwise
def point_on_segment(p, a, b, eps=EPS):
    if orientation(a, b, p, eps) != 0:
        return False

    return (
        min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps
    )


def segment_intersects(a, b, c, d, eps=EPS):
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


# Return the signed area of the polygon defined by the list of points
def polygon_signed_area(points: list[Point]) -> float:
    if len(points) < 3:
        return 0.0

    total = 0.0

    for i in range(len(points)):
        current = points[i]
        next_point = points[(i + 1) % len(points)]

        total += current.x * next_point.y
        total -= current.y * next_point.x

    return total / 2


# Return the area of the polygon defined by the list of points
def polygon_area(points):
    return abs(polygon_signed_area(points))


# Return the length of a polyline defined by the list of points
def polyline_length(points):
    total = 0.0

    for i in range(len(points) - 1):
        total += distance(points[i], points[i + 1])

    return total


# Return True if point p is inside the polygon defined by the list of points, False otherwise
def point_in_polygon(p, polygon, eps=EPS):
    if len(polygon) < 3:
        return False

    inside = False

    for i in range(len(polygon)):
        a = polygon[i]
        b = polygon[(i + 1) % len(polygon)]

        # Treat points on the boundary as inside
        if point_on_segment(p, a, b, eps):
            return True

        # Check whether the horizontal ray to the right crosses this edge
        crosses_ray = (a.y > p.y) != (b.y > p.y)

        if crosses_ray:
            x_intersection = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)

            if x_intersection > p.x:
                inside = not inside

    return inside