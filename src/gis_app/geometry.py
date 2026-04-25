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

# Return True if a and b are almost equal, False otherwise
def almost_equal(a, b, eps=EPS):
    return abs(a - b) < eps

# Return the distance between points p and q
def distance(p, q):
    # sqrt((p.x - q.x)^2 + (p.y - q.y)^2)
    return math.dist(p, q)

# Return what is the directioin of the turn formed by points a, b, c
def orientation(a, b, c):
    # Calculate the cross product of vectors (b-a) and (c-b)
    cross_product = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
    if almost_equal(cross_product, 0):
        return 0  # Collinear
    return 1 if cross_product > 0 else -1  # Clockwise or Counterclockwise

# Return True if the bounding boxes of box1 and box2 intersect, False otherwise
def bbox_intersects(box1, box2): # box is a Box object
    if (box1.max_x > box2.min_x and box1.min_x < box2.max_x and
        box1.max_y > box2.min_y and box1.min_y < box2.max_y):
        return True
    return False

# Return True if point p is on the line segment defined by points a and b, False otherwise
def point_on_segment(p, a, b, eps=EPS):
    if orientation(a, b, p) != 0:
        return False
    if (min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps and
        min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps):
        return True

def segment_intersects(a, b, c, d, eps=EPS):
    

def polygon_area(points):
    pass

def point_in_polygon(p, polygon):
    pass


