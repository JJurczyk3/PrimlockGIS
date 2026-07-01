"""Data models for grid generation."""

from dataclasses import dataclass


@dataclass
class GridModel:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    x_divisions: int
    y_divisions: int
    node_values: list[list[float]]

    def __post_init__(self) -> None:
        expected_rows = self.y_divisions + 1
        expected_cols = self.x_divisions + 1

        if len(self.node_values) != expected_rows:
            raise ValueError("node_values row count does not match y_divisions")

        for row in self.node_values:
            if len(row) != expected_cols:
                raise ValueError("node_values column count does not match x_divisions")

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
        self.node_values[row][col] = value
    

    def grid_intersection(self, row: int, col: int) -> tuple[float, float, float]:
        """Return x, y, z at the selected grid row and column."""
        self._validate_node_indices(row, col)

        x = self.node_x(col)
        y = self.node_y(row)
        z = self.node_value(row, col)
        return x, y, z

    def _validate_node_indices(self, row: int, col: int) -> None:
        if row < 0 or row > self.y_divisions:
            raise ValueError("Grid row is out of bounds")

        if col < 0 or col > self.x_divisions:
            raise ValueError("Grid column is out of bounds")
