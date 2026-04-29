"""A 2D renderer for the terminal."""

from primelock_gis.core.rendering.renderer_base import RendererBase
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.core.rendering.scene import (
    DrawablePoint,
    DrawablePolyline,
    DrawablePolygon,
    DrawableText,
    Scene,
)
from primelock_gis.ui.terminal.canvas import TerminalCanvas
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.core.geometry import Point


class TerminalRenderer2D(RendererBase):
    def __init__(
        self,
        canvas: TerminalCanvas,
        viewport: Viewport,
        capabilities: TerminalCapabilities,
    ) -> None:
        self.canvas = canvas
        self.viewport = viewport
        self.capabilities = capabilities
    
    def clear(self) -> None:
        self.canvas.clear()

    # Render points
    def draw_point(self, drawable: DrawablePoint) -> None:
        cell_x, cell_y = self._world_point_to_cell(drawable.position)
        self.canvas.set_cell(cell_x, cell_y, drawable.style.char)

    # Render polylines
    def draw_polyline(self, drawable: DrawablePolyline) -> None:
        cell_points = self._world_points_to_cell_points(drawable.points)
        self._draw_cell_polyline(cell_points, drawable.style.char, close=False)
            
    # Render polygons
    def draw_polygon(self, drawable: DrawablePolygon) -> None:
        cell_points = self._world_points_to_cell_points(drawable.points)
        self._draw_cell_polyline(cell_points, drawable.style.char, close=True)

    # Render text
    def draw_text(self, drawable: DrawableText) -> None:
        cell_x, cell_y = self._world_point_to_cell(drawable.position)
        self.canvas.write_text(cell_x, cell_y, drawable.text)

    # Render scene
    def render_scene(self, scene: Scene) -> None:
        super().render_scene(scene)

    # Output as a string on a screen.
    def to_string(self) -> str:
        return self.canvas.to_string()
    
    """ Helpers """
    # Convert world coordinates of a single point to screen coordinates.
    def _world_point_to_cell(self, point: Point) -> tuple[int, int]:
        view_point = self.viewport.world_to_view(point.x, point.y)
        return round(view_point.x), round(view_point.y)

    # Convert world coordinates of polyline nodes to screen coordinates.
    def _world_points_to_cell_points(self, points: list[Point]) -> list[tuple[int, int]]:
        return [self._world_point_to_cell(point) for point in points]
    
    # Draw connected line segments between terminal cell coordinates.
    def _draw_cell_polyline(self, cell_points: list[tuple[int, int]], char: str, close: bool = False) -> None:
        if len(cell_points) < 2:
            return

        for i in range(len(cell_points) - 1):
            x1, y1 = cell_points[i]
            x2, y2 = cell_points[i + 1]
            self._draw_line_cells(x1, y1, x2, y2, char)

        if close:
            x1, y1 = cell_points[-1]
            x2, y2 = cell_points[0]
            self._draw_line_cells(x1, y1, x2, y2, char)

    # Draw a sampled line between two terminal cells.
    def _draw_line_cells(self, x1: int, y1: int, x2: int, y2: int, char: str) -> None:
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))

        if steps == 0:
            self.canvas.set_cell(x1, y1, char)
            return

        for step in range(steps + 1):
            t = step / steps
            cell_x = round(x1 + dx * t)
            cell_y = round(y1 + dy * t)
            self.canvas.set_cell(cell_x, cell_y, char)


