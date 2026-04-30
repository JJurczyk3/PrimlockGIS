# inverse-distance-square interpolation
# directional weighted interpolation

from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.geometry import EPS, Point, distance_squared


def idw_value(points: list[SpecialPoint], x_a: float, y_a: float) -> float:
    """Calculate an interpolated z value using inverse-distance-square weighting."""
    if not points:
        raise ValueError("Cannot interpolate from an empty point list")

    target = Point(x_a, y_a)
    weight_sum = 0.0
    weighted_z_sum = 0.0

    for point in points:
        dist_sq = distance_squared(point, target)
        if dist_sq < EPS:
            return point.z

        weight = 1.0 / dist_sq
        weight_sum += weight
        weighted_z_sum += weight * point.z

    return weighted_z_sum / weight_sum
