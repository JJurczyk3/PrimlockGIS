"""Algorithms for handling grid models."""

from primelock_gis.core.models.vector import SpecialPoint
from primelock_gis.core.geometry import Box
from primelock_gis.core.models.grid import GridModel
from .interpolation import idw_value, directional_weighted_average


def get_point_bounds(points: list[SpecialPoint]) -> Box:
    if not points:
        raise ValueError("Cannot get bounds from an empty point list")

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)

    return Box(min_x, min_y, max_x, max_y)
    

def create_empty_grid_model(
    points: list[SpecialPoint],
    x_divisions: int,
    y_divisions: int,
) -> GridModel:
    
    if not isinstance(x_divisions, int) or not isinstance(y_divisions, int):
        raise ValueError("Grid divisions must be integers")
    if x_divisions < 1 or y_divisions < 1:
        raise ValueError("Grid divisions must be positive")

    bounds = get_point_bounds(points)
    rows = y_divisions + 1
    cols = x_divisions + 1

    node_values = []
    for _ in range(rows):
        grid_row = []
        for _ in range(cols):
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


def create_grid_model_idw(
        points: list[SpecialPoint], 
        x_divisions: int, 
        y_divisions: int,
) -> GridModel:
    """Create a grid model using inverse-distance-square interpolation."""
    grid_model = create_empty_grid_model(points, x_divisions, y_divisions)

    return _fill_grid_model(grid_model, points, idw_value)


def create_grid_model_directional(
        points: list[SpecialPoint], 
        x_divisions: int, 
        y_divisions: int, 
        sectors_per_quadrant: int=1,
) -> GridModel:
    """Create a grid model using directional weighted average interpolation."""
    grid_model = create_empty_grid_model(points, x_divisions, y_divisions)

    def interpolate(points, x, y):
        return directional_weighted_average(points, x, y, sectors_per_quadrant)
    
    return _fill_grid_model(grid_model, points, interpolate)


def _fill_grid_model(
    grid_model: GridModel,
    points: list[SpecialPoint],
    interpolation_function,
) -> GridModel:
    """Fill every grid node using the provided interpolation function."""
    for row in range(grid_model.y_divisions + 1):
        for col in range(grid_model.x_divisions + 1):
            x = grid_model.node_x(col)
            y = grid_model.node_y(row)
            z = interpolation_function(points, x, y)

            grid_model.node_values[row][col] = z
    return grid_model


def densify_grid_model(grid: GridModel, x_splits: int, y_splits: int) -> GridModel:
    """Densify the grid model by spliting rows and columns."""
    new_x_divisions = grid.x_divisions * x_splits
    new_y_divisions = grid.y_divisions * y_splits
  
    node_values = []

    for new_row in range(new_x_divisions + 1):
        grid_row = []

        for new_col in range(new_y_divisions + 1):
            # Find which old grid cell this new node lies in
            old_row = new_row // y_splits
            old_col = new_col // x_splits 

            # If the new node is on the top boundary, use the last old cell row
            if old_row == grid.y_divisions:
                old_row = grid.y_divisions - 1

            # If the new node is on the right boundary, use the last old cell column.
            if old_col == grid.x_divisions:
                old_col = grid.x_divisions - 1

            # Coordinates in the new local system
            u = (new_col - old_col * x_splits) / x_splits
            v = (new_row - old_row * y_splits) / y_splits

            z = _bilinear_interpolation_at_cell(grid, old_row, old_col, u, v)
            grid.row.append(z)
        node_values.append(grid_row)

    return GridModel(
        x_min=grid.x_min,
        y_min=grid.y_min,
        x_max=grid.x_max,
        y_max=grid.y_max,
        x_divisions=new_x_divisions,
        y_divisions=new_y_divisions,
        node_values=node_values,
    )


def _bilinear_interpolation_at_cell(
        grid: GridModel,
        row: int,
        col: int,
        u: float,
        v: float,
) -> float:
    """Interpolate inside one old grid cell."""
    z00 = grid.node_value(row, col)
    z10 = grid.node_value(row, col + 1)
    z01 = grid.node_value(row + 1, col)
    z11 = grid.node_value(row + 1, col + 1)
    
    return (
        z00 * (1 - u) * (1 - v)
        + z10 * u * (1 - v)
        + z01 * (1 - u) * v
        + z11 * u * v
    )