"""Algorithms for handling grid models."""

from collections.abc import Callable
from math import isfinite

from primelock_gis.core.geometry import Box
from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.vector import SpecialPoint

from .interpolation import directional_weighted_average, idw_value

InterpolationFunction = Callable[[list[SpecialPoint], float, float], float]


def get_point_bounds(points: list[SpecialPoint]) -> Box:
    """Return the axis-aligned x/y bounds of sample points."""
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
    """Create a zero-filled grid covering the source point bounds."""
    if not isinstance(x_divisions, int) or not isinstance(y_divisions, int):
        raise ValueError("Grid divisions must be integers")
    if x_divisions < 1 or y_divisions < 1:
        raise ValueError("Grid divisions must be positive")

    _validate_finite_sample_points(points)
    bounds = get_point_bounds(points)
    # A grid with N divisions has N + 1 stored nodes along that axis.
    rows = y_divisions + 1
    cols = x_divisions + 1

    node_values = [[0.0] * cols for _ in range(rows)]

    return GridModel(
        x_min=bounds.min_x,
        y_min=bounds.min_y,
        x_max=bounds.max_x,
        y_max=bounds.max_y,
        x_divisions=x_divisions,
        y_divisions=y_divisions,
        node_values=node_values,
    )


def _validate_finite_sample_points(points: list[SpecialPoint]) -> None:
    """Reject coordinates and elevations that cannot define a finite grid."""
    for point in points:
        for field_name, value in (
            ("x", point.x),
            ("y", point.y),
            ("z", point.z),
        ):
            if not isfinite(value):
                raise ValueError(
                    f"Sample point {point.id} {field_name} value must be finite"
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
    sectors_per_quadrant: int = 1,
) -> GridModel:
    """Create a grid model using directional weighted average interpolation."""
    grid_model = create_empty_grid_model(points, x_divisions, y_divisions)

    def interpolate(
        sample_points: list[SpecialPoint],
        x: float,
        y: float,
    ) -> float:
        return directional_weighted_average(
            sample_points,
            x,
            y,
            sectors_per_quadrant,
        )

    return _fill_grid_model(grid_model, points, interpolate)


def _fill_grid_model(
    grid_model: GridModel,
    points: list[SpecialPoint],
    interpolation_function: InterpolationFunction,
) -> GridModel:
    """Fill every grid node using the provided interpolation function."""
    for row in range(grid_model.y_divisions + 1):
        for col in range(grid_model.x_divisions + 1):
            x = grid_model.node_x(col)
            y = grid_model.node_y(row)
            z = interpolation_function(points, x, y)

            grid_model.set_node_value(row, col, z)
    return grid_model


def densify_grid_model(grid: GridModel, x_splits: int, y_splits: int) -> GridModel:
    """Densify the grid model by splitting each cell into smaller cells."""
    if not isinstance(x_splits, int) or not isinstance(y_splits, int):
        raise ValueError("Grid splits must be integers")
    if x_splits < 1 or y_splits < 1:
        raise ValueError("Grid splits must be positive")

    new_x_divisions = grid.x_divisions * x_splits
    new_y_divisions = grid.y_divisions * y_splits

    node_values = []

    for new_row in range(new_y_divisions + 1):
        grid_row = []

        for new_col in range(new_x_divisions + 1):
            old_row, v = _source_cell_position(
                new_row,
                y_splits,
                grid.y_divisions,
            )
            old_col, u = _source_cell_position(
                new_col,
                x_splits,
                grid.x_divisions,
            )

            z = _bilinear_interpolation_at_cell(grid, old_row, old_col, u, v)
            grid_row.append(z)
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


def _source_cell_position(
    new_index: int,
    split_count: int,
    source_divisions: int,
) -> tuple[int, float]:
    """Map a densified node index to its source cell and local fraction."""
    source_index = min(new_index // split_count, source_divisions - 1)
    fraction = (new_index - source_index * split_count) / split_count
    return source_index, fraction


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

    return z00 * (1 - u) * (1 - v) + z10 * u * (1 - v) + z01 * (1 - u) * v + z11 * u * v
