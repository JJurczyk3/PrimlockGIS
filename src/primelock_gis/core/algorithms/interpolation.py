"""Interpolation algorithms used when building grid models."""

from math import atan2, tau

from primelock_gis.core.geometry import EPS, Point, distance_squared
from primelock_gis.core.models.vector import SpecialPoint


def idw_value(points: list[SpecialPoint], target_x: float, target_y: float) -> float:
    """Calculate an interpolated z value using inverse-distance-square weighting."""
    if not points:
        raise ValueError("Cannot interpolate from an empty point list")

    target = Point(target_x, target_y)
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


def directional_weighted_average(
    points: list[SpecialPoint],
    target_x: float,
    target_y: float,
    sectors_per_quadrant: int = 1,
) -> float:
    """Apply IDW to the nearest sample in each angular sector."""
    if not points:
        raise ValueError("Cannot interpolate from an empty point list")

    if sectors_per_quadrant < 1:
        raise ValueError("sectors_per_quadrant must be positive")

    target = Point(target_x, target_y)
    sector_count = 4 * sectors_per_quadrant
    sector_size = tau / sector_count

    # One nearest sample per sector reduces directional clustering bias.
    nearest_by_sector: list[SpecialPoint | None] = [None] * sector_count
    nearest_distances = [float("inf")] * sector_count

    for point in points:
        dist_sq = distance_squared(point, target)

        if dist_sq < EPS:
            return point.z

        dx = point.x - target.x
        dy = point.y - target.y
        angle = atan2(dy, dx)

        if angle < 0:
            angle += tau

        sector_index = int(angle / sector_size)

        # Guard against rounding at the full-circle boundary.
        if sector_index == sector_count:
            sector_index = sector_count - 1

        if dist_sq < nearest_distances[sector_index]:
            nearest_by_sector[sector_index] = point
            nearest_distances[sector_index] = dist_sq

    selected_points = [point for point in nearest_by_sector if point is not None]
    return idw_value(selected_points, target_x, target_y)
