"""Data models for grid generation."""

from dataclasses import dataclass
from math import isfinite


@dataclass
class GridModel:
    """A regular elevation grid with divisions and stored boundary nodes.

    A grid with N divisions stores N + 1 nodes on that axis. Both spatial
    extents must be non-zero so interpolation within a cell is well-defined.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float
    x_divisions: int
    y_divisions: int
    node_values: list[list[float]]

    def __post_init__(self) -> None:
        if not isinstance(self.x_divisions, int) or not isinstance(
            self.y_divisions,
            int,
        ):
            raise ValueError("Grid divisions must be integers")
        if self.x_divisions < 1 or self.y_divisions < 1:
            raise ValueError("Grid divisions must be positive")
        if not all(
            isfinite(value)
            for value in (self.x_min, self.y_min, self.x_max, self.y_max)
        ):
            raise ValueError("Grid bounds must be finite")
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("Grid bounds must have positive width and height")

        expected_rows = self.y_divisions + 1
        expected_cols = self.x_divisions + 1

        if len(self.node_values) != expected_rows:
            raise ValueError("node_values row count does not match y_divisions")

        for row in self.node_values:
            if len(row) != expected_cols:
                raise ValueError("node_values column count does not match x_divisions")
            if not all(isfinite(value) for value in row):
                raise ValueError("Grid node values must be finite")

    @property
    def dx(self) -> float:
        return (self.x_max - self.x_min) / self.x_divisions

    @property
    def dy(self) -> float:
        return (self.y_max - self.y_min) / self.y_divisions

    def node_x(self, col: int) -> float:
        return self.x_min + col * self.dx

    def node_y(self, row: int) -> float:
        return self.y_min + row * self.dy

    def node_value(self, row: int, col: int) -> float:
        self._validate_node_indices(row, col)
        return self.node_values[row][col]

    def set_node_value(self, row: int, col: int, value: float) -> None:
        """Set the z value at one grid node."""
        self._validate_node_indices(row, col)
        if not isfinite(value):
            raise ValueError("Grid node value must be finite")
        self.node_values[row][col] = value

    def grid_intersection(self, row: int, col: int) -> tuple[float, float, float]:
        """Return x, y, z at the selected grid row and column."""
        self._validate_node_indices(row, col)

        x = self.node_x(col)
        y = self.node_y(row)
        z = self.node_value(row, col)
        return x, y, z

    def contains_xy(self, x: float, y: float) -> bool:
        """Return True if a world coordinate lies inside the grid bounds."""
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def bounds(self) -> tuple[float, float, float, float]:
        """Return x/y bounds as x_min, y_min, x_max, y_max."""
        return self.x_min, self.y_min, self.x_max, self.y_max

    def value_range(self) -> tuple[float, float]:
        """Return the minimum and maximum stored node values."""
        values = [value for row in self.node_values for value in row]
        return min(values), max(values)

    def sample_at(self, x: float, y: float) -> float | None:
        """Return a bilinearly interpolated value or None outside the grid."""
        if not self.contains_xy(x, y):
            return None

        col = min(
            self.x_divisions - 1,
            max(0, int((x - self.x_min) / self.dx)),
        )
        row = min(
            self.y_divisions - 1,
            max(0, int((y - self.y_min) / self.dy)),
        )
        u = (x - self.node_x(col)) / self.dx
        v = (y - self.node_y(row)) / self.dy

        z00 = self.node_value(row, col)
        z10 = self.node_value(row, col + 1)
        z01 = self.node_value(row + 1, col)
        z11 = self.node_value(row + 1, col + 1)

        return (
            z00 * (1 - u) * (1 - v)
            + z10 * u * (1 - v)
            + z01 * (1 - u) * v
            + z11 * u * v
        )

    def value_at(self, x: float, y: float) -> float:
        """Return a bilinearly interpolated grid value at a world coordinate."""
        value = self.sample_at(x, y)
        if value is None:
            raise ValueError("Point is outside grid bounds")

        return value

    def _validate_node_indices(self, row: int, col: int) -> None:
        if row < 0 or row > self.y_divisions:
            raise ValueError("Grid row is out of bounds")

        if col < 0 or col > self.x_divisions:
            raise ValueError("Grid column is out of bounds")
