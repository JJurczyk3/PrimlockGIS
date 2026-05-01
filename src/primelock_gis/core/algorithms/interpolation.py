"""Define inverse-distance-square interpolation and directional weighted average interpolation algorithms."""

from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.geometry import EPS, Point, distance_squared
from math import atan2, pi


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


def directional_weighted_average(points: list[SpecialPoint], x_a: float, y_a: float, sectors_per_quadrant: int = 1) -> float:
    """Calculate an interpolated z value using directional weighted average interpolation."""
    if not points:
        raise ValueError("Cannot interpolate from an empty point list")
    
    if sectors_per_quadrant < 1:
        raise ValueError("sectors_per_quadrant must be positive")
    
    target = Point(x_a, y_a)
    sector_count = 4 * sectors_per_quadrant
    sector_size = 2 * pi / sector_count

    nearest_by_sector = [None for _ in range(sector_count)]
    nearest_distances = [float("inf") for _ in range(sector_count)]

    for point in points:
        dist_sq = distance_squared(point, target)

        if dist_sq < EPS:
            return point.z
        
        dx = point.x - target.x
        dy = point.y - target.y
        angle = atan2(dy, dx) # angle from -pi to pi

        if angle < 0:
            angle += 2 * pi # so angle from 0 to 2pi

        sector_index = int(angle / sector_size)       

        # prevent rare cases where sector index_rounds up to sector_count for angles near to 2pi
        if sector_index == sector_count:
            sector_index = sector_count - 1

        if dist_sq < nearest_distances[sector_index]:
            nearest_by_sector[sector_index] = point
            nearest_distances[sector_index] = dist_sq

    selected_points = [
        point for point in nearest_by_sector
        if point is not None
    ]
    return idw_value(selected_points, x_a, y_a)



