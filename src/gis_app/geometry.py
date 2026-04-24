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

def almost_equal(a, b, eps=EPS):
    pass

def distance(p, q):
    pass

def orientation():
    pass

def bbox_intersects(box1, box2):
    pass

def point_on_segment(p, a, b, eps=EPS):
    pass

def segment_intersects(a, b, c, d, eps=EPS):
    pass

def polygon_area(points):
    pass

def point_in_polygon(p, polygon):
    pass


