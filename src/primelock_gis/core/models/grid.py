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
        return self.node_values[row][col]
   