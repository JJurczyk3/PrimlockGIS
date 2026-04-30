"""Algorithms for handling grid models."""
from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.geometry import Box
from primelock_gis.core.models.grid import GridModel
from .interpolation import idw_value


def get_point_bounds(points: list[SpecialPoint]) -> Box:
    if not points:
        raise ValueError("Cannot get bounds from an empty point list")

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)

    return Box(min_x, min_y, max_x, max_y)
    

def create_empty_grid_model(
    x_divisions: int,
    y_divisions: int,
    points: list[SpecialPoint],
) -> GridModel:
    
    if not isinstance(x_divisions, int) or not isinstance(y_divisions, int):
        raise ValueError("Grid divisions must be integers")
    if x_divisions < 1 or y_divisions < 1:
        raise ValueError("Grid divisions must be positive")

    bounds = get_point_bounds(points)
    rows = y_divisions + 1
    cols = x_divisions + 1

    node_values = []
    for row in range(rows):
        grid_row = []
        for col in range(cols):
            grid_row.append(0.0)

        node_values.append(grid_row)

    return GridModel(
        x_min=bounds.min_x,
        y_min=bounds.min_y,
        x_max=bounds.max_x,
        y_max=bounds.max_y,
        x_divisions=x_divisions,
        y_divisions=y_divisions,
        node_values=node_values,
    )


def create_grid_model_idw(x_divisions: int, y_divisions: int, points: list[SpecialPoint]) -> GridModel:
    """Create a grid model using inverse-distance-square interpolation."""
    grid_model = create_empty_grid_model(x_divisions, y_divisions, points)

    for row in range(y_divisions + 1):
        for col in range(x_divisions + 1):
            x = grid_model.node_x(col)
            y = grid_model.node_y(row)
            z = idw_value(points, x, y)

            grid_model.node_value(row, col) = z
    return grid_model