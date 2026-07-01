""" A 2D renderer for the terminal. """

from primelock_gis.core.rendering.renderer_base import RendererBase
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.core.rendering.scene import (
    DrawableTerrain,
    DrawablePoint,
    DrawablePolyline,
    DrawablePolygon,
    DrawableText,
    Scene,
)
from primelock_gis.ui.terminal.canvas import TerminalCanvas
from primelock_gis.ui.terminal.canvas import parse_hex_color
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.core.geometry import Point


OPPOSITE_DIRECTIONS = {
    "left": "right",
    "right": "left",
    "up": "down",
    "down": "up",
}

BRAILLE_SUBCELL_WIDTH = 2
BRAILLE_SUBCELL_HEIGHT = 4
CELL_ALIGNMENT_TOLERANCE = 0.05


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

    def draw_terrain(self, drawable: DrawableTerrain) -> None:
        """Render a grid-backed terrain colour layer as cell backgrounds."""
        grid = drawable.grid
        if not self._grid_intersects_view(grid):
            return

        value_min = min(min(row) for row in grid.node_values)
        value_max = max(max(row) for row in grid.node_values)

        for cell_y in range(self.canvas.height):
            for cell_x in range(self.canvas.width):
                world_point = self.viewport.view_to_world(cell_x + 0.5, cell_y + 0.5)
                if not grid.contains_xy(world_point.x, world_point.y):
                    continue

                value = grid.value_at(world_point.x, world_point.y)
                color = self._terrain_color(
                    value,
                    value_min,
                    value_max,
                    drawable.style,
                )
                self.canvas.set_background_cell(
                    cell_x,
                    cell_y,
                    color,
                    char=drawable.style.char,
                )

    # Render points
    def draw_point(self, drawable: DrawablePoint) -> None:
        if not self._point_intersects_view(drawable.position):
            return

        cell_x, cell_y = self._world_point_to_cell(drawable.position)
        self.canvas.set_cell(
            cell_x,
            cell_y,
            drawable.style.char,
            foreground=drawable.style.color,
        )

    # Render polylines
    def draw_polyline(self, drawable: DrawablePolyline) -> None:
        if not self._points_intersect_view(drawable.points):
            return

        view_points = self._world_points_to_view_points(drawable.points)
        if self._should_draw_polyline_with_braille(view_points, drawable.style):
            self._draw_braille_view_polyline(view_points, drawable.style, close=False)
            return

        cell_points = self._world_points_to_cell_points(drawable.points)
        self._draw_cell_polyline(cell_points, drawable.style, close=False)
            
    # Render polygons
    def draw_polygon(self, drawable: DrawablePolygon) -> None:
        if not self._points_intersect_view(drawable.points):
            return

        cell_points = self._world_points_to_cell_points(drawable.points)
        self._draw_literal_cell_polyline(
            cell_points,
            drawable.style.char,
            color=drawable.style.outline_color,
            close=True,
        )

    # Render text
    def draw_text(self, drawable: DrawableText) -> None:
        if not self._point_intersects_view(drawable.position):
            return

        cell_x, cell_y = self._world_point_to_cell(drawable.position)
        self.canvas.write_text(
            cell_x,
            cell_y,
            drawable.text,
            foreground=drawable.style.color,
        )

    # Render scene
    def render_scene(self, scene: Scene) -> None:
        super().render_scene(scene)

    # Output as a string on a screen.
    def to_string(self) -> str:
        return self.canvas.to_string(self.capabilities)

    def _point_intersects_view(self, point: Point) -> bool:
        return (
            self.viewport.world_min_x <= point.x <= self.viewport.world_max_x
            and self.viewport.world_min_y <= point.y <= self.viewport.world_max_y
        )

    def _points_intersect_view(self, points: list[Point]) -> bool:
        if not points:
            return False

        min_x = min(point.x for point in points)
        max_x = max(point.x for point in points)
        min_y = min(point.y for point in points)
        max_y = max(point.y for point in points)

        return not (
            max_x < self.viewport.world_min_x
            or min_x > self.viewport.world_max_x
            or max_y < self.viewport.world_min_y
            or min_y > self.viewport.world_max_y
        )

    def _grid_intersects_view(self, grid) -> bool:
        return not (
            grid.x_max < self.viewport.world_min_x
            or grid.x_min > self.viewport.world_max_x
            or grid.y_max < self.viewport.world_min_y
            or grid.y_min > self.viewport.world_max_y
        )

    def _terrain_color(self, value: float, value_min: float, value_max: float, style) -> str:
        if value_max == value_min:
            return style.low_mid_color

        t = (value - value_min) / (value_max - value_min)
        t = max(0.0, min(1.0, t))

        stops = (
            (0.0, style.low_color),
            (0.35, style.low_mid_color),
            (0.7, style.high_mid_color),
            (1.0, style.high_color),
        )

        for index in range(len(stops) - 1):
            start_t, start_color = stops[index]
            end_t, end_color = stops[index + 1]
            if start_t <= t <= end_t:
                local_t = (t - start_t) / (end_t - start_t)
                return self._interpolate_hex_color(start_color, end_color, local_t)

        return style.high_color

    def _interpolate_hex_color(
        self,
        start_color: str,
        end_color: str,
        t: float,
    ) -> str:
        start_rgb = parse_hex_color(start_color)
        end_rgb = parse_hex_color(end_color)
        if start_rgb is None or end_rgb is None:
            return start_color

        red = round(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
        green = round(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
        blue = round(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
        return f"#{red:02X}{green:02X}{blue:02X}"
    
    # Convert world coordinates of a single point to screen coordinates.
    def _world_point_to_cell(self, point: Point) -> tuple[int, int]:
        view_point = self.viewport.world_to_view(point.x, point.y)
        return (
            self._view_coordinate_to_cell(view_point.x, self.canvas.width),
            self._view_coordinate_to_cell(view_point.y, self.canvas.height),
        )

    # Convert one view coordinate to a drawable terminal cell index.
    def _view_coordinate_to_cell(self, value: float, size: int) -> int:
        cell = round(value)

        if 0 <= value <= size:
            return max(0, min(size - 1, cell))

        return cell

    # Convert world coordinates of polyline nodes to screen coordinates.
    def _world_points_to_cell_points(self, points: list[Point]) -> list[tuple[int, int]]:
        return [self._world_point_to_cell(point) for point in points]

    # Convert world coordinates of polyline nodes to fractional view coordinates.
    def _world_points_to_view_points(
        self,
        points: list[Point],
    ) -> list[tuple[float, float]]:
        view_points = []

        for point in points:
            view_point = self.viewport.world_to_view(point.x, point.y)
            view_points.append((view_point.x, view_point.y))

        return view_points
    
    # Draw connected line segments between terminal cell coordinates.
    def _draw_cell_polyline(self, cell_points, style, close: bool = False) -> None:
        if len(cell_points) < 2:
            return

        if style.line_type == "literal":
            self._draw_literal_cell_polyline(
                cell_points,
                style.char,
                color=style.color,
                close=close,
            )
            return

        points = list(cell_points)

        if close:
            points.append(cell_points[0])

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self._draw_styled_line_cells(x1, y1, x2, y2, style)

    def _draw_literal_cell_polyline(
        self,
        cell_points: list[tuple[int, int]],
        char: str,
        color: str | None = None,
        close: bool = False,
    ) -> None:
        if len(cell_points) < 2:
            return

        points = list(cell_points)

        if close:
            points.append(cell_points[0])

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self._draw_literal_line_cells(x1, y1, x2, y2, char, color)

    # Draw a sampled line between two terminal cells.
    def _sample_line_cells(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> list[tuple[int, int]]:
        return list(self._iter_sampled_line_cells(x1, y1, x2, y2))

    def _iter_sampled_line_cells(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ):
        """Yield sampled line cells without allocating a temporary list."""
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))

        if steps == 0:
            yield (x1, y1)
            return

        previous_cell = None

        for step in range(steps + 1):
            t = step / steps
            cell_x = round(x1 + dx * t)
            cell_y = round(y1 + dy * t)
            cell = (cell_x, cell_y)

            if cell != previous_cell:
                yield cell
                previous_cell = cell

    def _draw_literal_line_cells(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        char: str,
        color: str | None,
    ) -> None:
        clipped = self._clip_line_to_rect(
            x1,
            y1,
            x2,
            y2,
            min_x=0,
            min_y=0,
            max_x=self.canvas.width - 1,
            max_y=self.canvas.height - 1,
        )
        if clipped is None:
            return

        x1, y1, x2, y2 = (round(value) for value in clipped)

        for cell_x, cell_y in self._iter_sampled_line_cells(x1, y1, x2, y2):
            self.canvas.set_cell(cell_x, cell_y, char, foreground=color)

    def _draw_styled_line_cells(self, x1: int, y1: int, x2: int, y2: int, style) -> None:
        clipped = self._clip_line_to_rect(
            x1,
            y1,
            x2,
            y2,
            min_x=0,
            min_y=0,
            max_x=self.canvas.width - 1,
            max_y=self.canvas.height - 1,
        )
        if clipped is None:
            return

        x1, y1, x2, y2 = (round(value) for value in clipped)
        cells = self._iter_sampled_line_cells(x1, y1, x2, y2)
        previous_cell = next(cells, None)

        if previous_cell is None:
            return

        drew_segment = False
        for index, current_cell in enumerate(cells):
            if self._line_pattern_visible(index, style.line_type):
                self._draw_styled_cell_pair(previous_cell, current_cell, style)
                drew_segment = True

            previous_cell = current_cell

        if not drew_segment:
            cell_x, cell_y = previous_cell
            self.canvas.set_cell(
                cell_x,
                cell_y,
                style.char,
                foreground=style.color,
            )

    def _line_pattern_visible(self, index: int, line_type: str) -> bool:
        if line_type == "dashed":
            return index % 6 < 4

        if line_type == "dotted":
            return index % 2 == 0

        return True

    def _draw_styled_cell_pair(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        style,
    ) -> None:
        start_x, start_y = start
        end_x, end_y = end
        dx = end_x - start_x
        dy = end_y - start_y

        if dx == 0 and dy == 0:
            return

        if abs(dx) + abs(dy) == 1:
            direction = self._direction_from_delta(dx, dy)
            self.canvas.set_line_cell(
                start_x,
                start_y,
                {direction},
                color=style.color,
                line_style=style.line_type,
            )
            self.canvas.set_line_cell(
                end_x,
                end_y,
                {OPPOSITE_DIRECTIONS[direction]},
                color=style.color,
                line_style=style.line_type,
            )
            return

        diagonal_char = self._diagonal_char(dx, dy)
        self.canvas.set_cell(
            start_x,
            start_y,
            diagonal_char,
            foreground=style.color,
        )
        self.canvas.set_cell(
            end_x,
            end_y,
            diagonal_char,
            foreground=style.color,
        )

    def _direction_from_delta(self, dx: int, dy: int) -> str:
        if dx < 0:
            return "left"
        if dx > 0:
            return "right"
        if dy < 0:
            return "up"
        return "down"

    def _diagonal_char(self, dx: int, dy: int) -> str:
        if self.capabilities.supports_unicode:
            if dx * dy > 0:
                return "╲"
            return "╱"

        if dx * dy > 0:
            return "\\"
        return "/"

    def _should_draw_polyline_with_braille(
        self,
        view_points: list[tuple[float, float]],
        style,
    ) -> bool:
        if style.line_type == "literal":
            return False
        if not self.capabilities.supports_unicode:
            return False
        if not self.capabilities.supports_braille:
            return False
        if len(view_points) < 2:
            return False
        if style.line_type == "braille":
            return True

        for index in range(len(view_points) - 1):
            if self._segment_needs_braille(view_points[index], view_points[index + 1]):
                return True

        return False

    def _segment_needs_braille(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> bool:
        start_x, start_y = start
        end_x, end_y = end
        dx = abs(end_x - start_x)
        dy = abs(end_y - start_y)

        if dx <= CELL_ALIGNMENT_TOLERANCE or dy <= CELL_ALIGNMENT_TOLERANCE:
            return False

        if abs(dx - dy) <= CELL_ALIGNMENT_TOLERANCE:
            return False

        return True

    def _draw_braille_view_polyline(
        self,
        view_points: list[tuple[float, float]],
        style,
        close: bool = False,
    ) -> None:
        if len(view_points) < 2:
            return

        points = list(view_points)

        if close:
            points.append(view_points[0])

        for index in range(len(points) - 1):
            start_x, start_y = points[index]
            end_x, end_y = points[index + 1]
            self._draw_braille_view_line(start_x, start_y, end_x, end_y, style)

    def _draw_braille_view_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        style,
    ) -> None:
        clipped = self._clip_line_to_rect(
            x1,
            y1,
            x2,
            y2,
            min_x=0,
            min_y=0,
            max_x=self.canvas.width,
            max_y=self.canvas.height,
        )
        if clipped is None:
            return

        x1, y1, x2, y2 = clipped
        start = self._view_point_to_braille_subcell(x1, y1)
        end = self._view_point_to_braille_subcell(x2, y2)

        for index, (sub_x, sub_y) in enumerate(
            self._iter_sampled_line_cells(start[0], start[1], end[0], end[1])
        ):
            if not self._braille_pattern_visible(index, style.line_type):
                continue

            cell_x = sub_x // BRAILLE_SUBCELL_WIDTH
            cell_y = sub_y // BRAILLE_SUBCELL_HEIGHT
            cell_sub_x = sub_x % BRAILLE_SUBCELL_WIDTH
            cell_sub_y = sub_y % BRAILLE_SUBCELL_HEIGHT

            self.canvas.set_braille_dot(
                cell_x,
                cell_y,
                cell_sub_x,
                cell_sub_y,
                color=style.color,
                line_style=style.line_type,
            )

    def _view_point_to_braille_subcell(
        self,
        x: float,
        y: float,
    ) -> tuple[int, int]:
        return (
            self._view_coordinate_to_subcell(
                x,
                self.canvas.width,
                BRAILLE_SUBCELL_WIDTH,
            ),
            self._view_coordinate_to_subcell(
                y,
                self.canvas.height,
                BRAILLE_SUBCELL_HEIGHT,
            ),
        )

    def _view_coordinate_to_subcell(
        self,
        value: float,
        size: int,
        scale: int,
    ) -> int:
        subcell = round(value * scale)

        if 0 <= value <= size:
            return max(0, min(size * scale - 1, subcell))

        return subcell

    def _braille_pattern_visible(self, index: int, line_type: str) -> bool:
        if line_type == "dashed":
            return index % 20 < 12

        if line_type == "dotted":
            return index % 5 == 0

        return True

    def _clip_line_to_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> tuple[float, float, float, float] | None:
        """Clip a line segment to a rectangle using Liang-Barsky clipping."""
        dx = x2 - x1
        dy = y2 - y1
        start_t = 0.0
        end_t = 1.0

        checks = (
            (-dx, x1 - min_x),
            (dx, max_x - x1),
            (-dy, y1 - min_y),
            (dy, max_y - y1),
        )

        for direction, distance in checks:
            if direction == 0:
                if distance < 0:
                    return None
                continue

            ratio = distance / direction

            if direction < 0:
                if ratio > end_t:
                    return None
                start_t = max(start_t, ratio)
            else:
                if ratio < start_t:
                    return None
                end_t = min(end_t, ratio)

        return (
            x1 + start_t * dx,
            y1 + start_t * dy,
            x1 + end_t * dx,
            y1 + end_t * dy,
        )
