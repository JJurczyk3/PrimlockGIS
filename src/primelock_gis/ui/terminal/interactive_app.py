"""Interactive terminal app set-up."""

from dataclasses import dataclass, field, replace
from pathlib import Path
import shutil
import time
from queue import Empty, Queue

from primelock_gis.app.project_builder import try_rebuild_project_state
from primelock_gis.app.project_state import ProjectConfig, ProjectState
from primelock_gis.core.algorithms.contour import (
    contour_polylines_from_tin,
    contour_segments_from_grid,
    generate_contour_levels,
    grid_value_range,
    tin_value_range,
    trace_contour_segments,
)
from primelock_gis.core.models.contour import ContourPolyline
from primelock_gis.core.rendering.scene import Scene
from primelock_gis.core.rendering.scene_builder import (
    contour_labels_to_scene,
    contour_polylines_to_scene,
    grid_to_scene,
    points_to_scene,
    tin_to_scene,
)
from primelock_gis.core.rendering.symbology import PointStyle, PolylineStyle
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.ui.terminal.events import KeyEvent, MouseEvent, TerminalEvent
from primelock_gis.ui.terminal.input import read_terminal_event
from primelock_gis.ui.terminal.render_app import TerminalRenderApp
from primelock_gis.ui.terminal.screen import clear_screen, present_frame
from primelock_gis.ui.terminal.session import TerminalSession
from primelock_gis.ui.terminal.support_panel import CommandRequest
from primelock_gis.ui.terminal.theme import TERMINAL_THEME, status_color


def coalesce_terminal_events(events: list[TerminalEvent]) -> list[TerminalEvent]:
    """Collapse redundant high-frequency pointer movement events.

    Press/release and key events are always preserved. Consecutive drag or
    wheel events are represented by the latest event, so rendering catches up
    to the user's current pointer position instead of replaying stale motion.
    """
    coalesced = []
    pending_motion: MouseEvent | None = None

    def flush_pending_mouse_motion() -> None:
        nonlocal pending_motion

        if pending_motion is not None:
            coalesced.append(pending_motion)
            pending_motion = None

    for event in events:
        if isinstance(event, MouseEvent) and event.kind == "drag":
            pending_motion = event
            continue

        if isinstance(event, MouseEvent) and event.kind in ("wheel_up", "wheel_down"):
            pending_motion = event
            continue

        flush_pending_mouse_motion()
        coalesced.append(event)

    flush_pending_mouse_motion()
    return coalesced


@dataclass
class InteractiveState:
    running: bool = True
    interaction_mode: str = "normal"
    show_points: bool = True
    show_grid: bool = False
    show_tin: bool = True
    show_contours: bool = False
    show_contour_labels: bool = False
    contour_source: str = "grid"
    contour_interval: float = 50.0
    debug_input_enabled: bool = False
    debug_input_events: list[str] = field(default_factory=list)
    selected_feature: str = "No feature selected."
    status_message: str = "Ready"


class InteractiveTerminalApp:
    """Run the interactive terminal GIS application."""

    CLICK_DRAG_THRESHOLD_CELLS = 1.5
    PENDING_CLICK_SECONDS = 0.12
    SELECTION_MAX_DISTANCE_CELLS = 4.0
    STATUS_ROWS = 2

    def __init__(
        self,
        project_state: ProjectState,
        viewport: Viewport,
        capabilities: TerminalCapabilities,
        command_queue: Queue[CommandRequest] | None = None,
    ) -> None:
        self.project_state = project_state
        self.viewport = viewport
        self.initial_viewport = viewport
        self.capabilities = capabilities
        self.command_queue = command_queue
        self.state = InteractiveState()
        self.state.contour_source = project_state.config.contour_source
        self.state.contour_interval = project_state.config.contour_interval
        self.render_app: TerminalRenderApp | None = None
        self.mouse_press_screen: tuple[int, int] | None = None
        self.last_mouse_screen: tuple[int, int] | None = None
        self.mouse_dragging: bool = False
        self.pending_click_screen: tuple[int, int] | None = None
        self.pending_click_started_at: float | None = None
        self.pending_click_previous_selection: tuple[str, str] | None = None
        self.pending_click_committed: bool = False
        self.scene_cache_key: tuple[
            bool,
            bool,
            bool,
            bool,
            bool,
            str,
            float,
        ] | None = None
        self.scene_cache: Scene | None = None
        self.contour_cache_key: tuple[str, float] | None = None
        self.contour_cache: list[ContourPolyline] | None = None
        self._frame_dirty = True
        self._screen_needs_clear = True

    def build_scene(self) -> Scene:
        """Build the currently visible scene from enabled layers."""
        cache_key = self._scene_visibility_cache_key()
        if self.scene_cache_key == cache_key and self.scene_cache is not None:
            return self.scene_cache

        scene = Scene()

        if self.state.show_grid:
            grid_scene = grid_to_scene(
                self.project_state.idw_grid,
                style=PolylineStyle(
                    color=TERMINAL_THEME.grid,
                    char=".",
                    line_type="solid",
                ),
            )
            self._merge_scene(scene, grid_scene)

        if self.state.show_tin:
            tin_scene = tin_to_scene(
                self.project_state.tin,
                style=PolylineStyle(
                    color=TERMINAL_THEME.tin,
                    char="*",
                    line_type="braille",
                ),
            )
            self._merge_scene(scene, tin_scene)

        if self.state.show_contours:
            contour_polylines = self.contour_polylines()
            contour_scene = contour_polylines_to_scene(
                contour_polylines,
                style=PolylineStyle(
                    color=TERMINAL_THEME.contours,
                    char="=",
                    line_type="braille",
                ),
            )
            self._merge_scene(scene, contour_scene)

        if self.state.show_points:
            point_scene = points_to_scene(
                self.project_state.points,
                style=PointStyle(
                    color=TERMINAL_THEME.points,
                    char="●",
                ),
            )
            self._merge_scene(scene, point_scene)

        if self.state.show_contours and self.state.show_contour_labels:
            label_scene = contour_labels_to_scene(self.contour_polylines())
            self._merge_scene(scene, label_scene)

        self.scene_cache_key = cache_key
        self.scene_cache = scene
        return scene

    def render_frame(self) -> str:
        """Render the current visible scene to terminal text."""
        scene = self.build_scene()

        render_app = self._render_app_for(scene)

        return render_app.redraw()

    def handle_key(self, key: str) -> None:
        """Handle one keyboard input event."""
        if key == "q":
            self.state.running = False
            return

        if key == "g":
            self.state.show_grid = not self.state.show_grid
            self.state.status_message = self._visibility_status(
                "Grid",
                self.state.show_grid,
            )
            return

        if key == "t":
            self.state.show_tin = not self.state.show_tin
            self.state.status_message = self._visibility_status(
                "TIN",
                self.state.show_tin,
            )
            return

        if key == "p":
            self.state.show_points = not self.state.show_points
            self.state.status_message = self._visibility_status(
                "Points",
                self.state.show_points,
            )
            return

        if key == "c":
            self.state.show_contours = not self.state.show_contours
            self.state.status_message = self._visibility_status(
                "Contours",
                self.state.show_contours,
            )
            return

        if key == "m":
            self._toggle_contour_source()
            return

        if key == "v":
            self.state.show_contour_labels = not self.state.show_contour_labels
            self.state.status_message = self._visibility_status(
                "Contour labels",
                self.state.show_contour_labels,
            )
            return

        if key == "[":
            self._scale_contour_interval(0.5)
            return

        if key == "]":
            self._scale_contour_interval(2.0)
            return

        if key == "r":
            self.viewport = self.initial_viewport
            self.state.status_message = "Viewport reset"
            return

        pan_key = self._pan_direction_from_key(key)
        if pan_key is not None:
            self._pan_with_key(pan_key)
            return

        if key in ("+", "="):
            self._zoom_at_view_center(1.25)
            return

        if key in ("-", "_"):
            self._zoom_at_view_center(0.8)
            return

        self.state.status_message = f"Unknown key: {repr(key)}"

    def handle_event(self, event: TerminalEvent) -> None:
        """Handle one terminal input event."""
        self._record_debug_event(event)

        if isinstance(event, KeyEvent):
            self.handle_key(event.key)
            return

        if isinstance(event, MouseEvent):
            self.handle_mouse(event)

    def handle_mouse(self, event: MouseEvent) -> None:
        """Handle one mouse input event."""
        if (
            event.x < 0
            or event.x >= self.viewport.view_width
            or event.y < 0
            or event.y >= self.viewport.view_height
        ):
            self._clear_mouse_drag_state()
            self._cancel_pending_click(restore_committed=True)
            return

        if event.kind == "press" and event.button == 0:
            self.mouse_press_screen = (event.x, event.y)
            self.last_mouse_screen = (event.x, event.y)
            self.mouse_dragging = False
            self._begin_pending_click(event.x, event.y)
            return

        if event.kind == "drag" and event.button == 0:
            self._update_mouse_drag_state(event.x, event.y)
            if self.mouse_dragging:
                self._cancel_pending_click(restore_committed=True)
            self._pan_with_mouse_drag(event.x, event.y)
            return

        if event.kind == "release":
            if self._is_click_release(event.x, event.y):
                self._commit_click_selection(event.x, event.y)

            self._clear_mouse_drag_state()
            self._clear_pending_click()
            return

        if event.kind == "wheel_up":
            self._zoom_at_screen(event.x, event.y, 1.2)
            return

        if event.kind == "wheel_down":
            self._zoom_at_screen(event.x, event.y, 1 / 1.2)
            return

    def resize_if_needed(self) -> int:
        """Resize viewport to match the terminal and return the status-row number."""
        terminal_size = shutil.get_terminal_size()
        width = terminal_size.columns
        height = max(1, terminal_size.lines - self.STATUS_ROWS)

        if width != self.viewport.view_width or height != self.viewport.view_height:
            self.viewport = self.viewport.resize_viewport(width, height)
            self.initial_viewport = self.initial_viewport.resize_viewport(width, height)
            self.state.status_message = f"Resized to {width}x{height}"
            self._frame_dirty = True
            self._screen_needs_clear = True

        return terminal_size.lines

    def run(self) -> None:
        """Run the interactive terminal application loop."""
        with TerminalSession():
            clear_screen()
            self._screen_needs_clear = False

            while self.state.running:
                if self.commit_pending_click_if_ready():
                    self._frame_dirty = True

                if self.process_support_commands():
                    self._frame_dirty = True

                status_row = self.resize_if_needed()
                events = self._read_ready_events(
                    timeout=0.0 if self._frame_dirty else 0.05,
                )
                if events:
                    for event in coalesce_terminal_events(events):
                        self.handle_event(event)
                    self._frame_dirty = True

                if self._frame_dirty:
                    if self._screen_needs_clear:
                        clear_screen()
                        self._screen_needs_clear = False

                    frame = self.render_frame()
                    present_frame(
                        frame=frame,
                        instruction_text=self.status_instruction_text(),
                        info_text=self.status_info_text(),
                        instruction_row=max(1, status_row - 1),
                        info_row=status_row,
                        width=self.viewport.view_width,
                        instruction_color=TERMINAL_THEME.muted,
                        info_color=status_color(self.status_info_text()),
                        capabilities=self.capabilities,
                    )
                    self._frame_dirty = False

    def _read_ready_events(self, timeout: float) -> list[TerminalEvent]:
        """Read the currently available terminal events without leaving a backlog."""
        first_event = read_terminal_event(timeout=timeout)
        if first_event is None:
            return []

        events = [first_event]

        while True:
            event = read_terminal_event(timeout=0.0)
            if event is None:
                break

            events.append(event)

        return events

    def status_instruction_text(self) -> str:
        """Return the controls row for the bottom status area."""
        return (
            "q quit | g grid | t TIN | p points | c contours | m source | "
            "v labels | [/] interval | r reset | hjkl pan | +/- zoom "
            f"| grid={self.state.show_grid} "
            f"| tin={self.state.show_tin} "
            f"| points={self.state.show_points} "
            f"| contours={self.state.show_contours} "
            f"| source={self.state.contour_source} "
            f"| interval={self.state.contour_interval:g} "
            f"| grid={self.project_state.config.grid_x_divisions}x"
            f"{self.project_state.config.grid_y_divisions}"
        )

    def status_info_text(self) -> str:
        """Return the information row for the bottom status area."""
        return self.state.status_message

    def _merge_scene(self, target: Scene, source: Scene) -> None:
        """Merge one scene into another scene."""
        target.polygons.extend(source.polygons)
        target.polylines.extend(source.polylines)
        target.points.extend(source.points)
        target.texts.extend(source.texts)

    def _scene_visibility_cache_key(
        self,
    ) -> tuple[bool, bool, bool, bool, bool, str, float]:
        """Return the state values that affect the static rendered scene."""
        return (
            self.state.show_grid,
            self.state.show_tin,
            self.state.show_points,
            self.state.show_contours,
            self.state.show_contour_labels,
            self.state.contour_source,
            self.state.contour_interval,
        )

    def contour_polylines(self) -> list[ContourPolyline]:
        """Return cached contour polylines for the current contour settings."""
        cache_key = (
            self.state.contour_source,
            self.state.contour_interval,
        )
        if self.contour_cache_key == cache_key and self.contour_cache is not None:
            return self.contour_cache

        if self.state.contour_source == "tin":
            value_min, value_max = tin_value_range(self.project_state.tin)
            levels = generate_contour_levels(
                value_min,
                value_max,
                self.state.contour_interval,
            )
            polylines = contour_polylines_from_tin(
                self.project_state.tin,
                levels,
                self.state.contour_interval,
            )
        else:
            value_min, value_max = grid_value_range(self.project_state.idw_grid)
            levels = generate_contour_levels(
                value_min,
                value_max,
                self.state.contour_interval,
            )
            segments = contour_segments_from_grid(
                self.project_state.idw_grid,
                levels,
                self.state.contour_interval,
            )
            polylines = trace_contour_segments(
                segments,
                self.project_state.idw_grid,
            )

        self.contour_cache_key = cache_key
        self.contour_cache = polylines
        return polylines

    def _toggle_contour_source(self) -> None:
        """Switch contour generation between the grid and TIN models."""
        if self.state.contour_source == "grid":
            self.state.contour_source = "tin"
        else:
            self.state.contour_source = "grid"

        self._update_project_config(contour_source=self.state.contour_source)
        self.state.status_message = (
            f"Contour source: {self.state.contour_source}"
        )

    def _scale_contour_interval(self, factor: float) -> None:
        """Scale the contour interval while keeping it positive and readable."""
        self.state.contour_interval = max(
            0.001,
            self.state.contour_interval * factor,
        )
        self._update_project_config(contour_interval=self.state.contour_interval)
        self.state.status_message = (
            f"Contour interval: {self.state.contour_interval:g}"
        )

    def _visibility_status(self, layer_name: str, visible: bool) -> str:
        """Return a short visibility status message."""
        if visible:
            return f"{layer_name} visible"

        return f"{layer_name} hidden"

    def _debug_event_status(self, event: TerminalEvent) -> str:
        """Return a status message showing one raw terminal input event."""
        raw_sequence = getattr(event, "raw_sequence", None)

        if raw_sequence is None:
            raw_sequence = repr(event)

        escaped = raw_sequence.encode("unicode_escape").decode("ascii")
        return f"Input debug: {type(event).__name__} raw={escaped}"

    def _record_debug_event(self, event: TerminalEvent) -> None:
        """Store one input event for support-panel debugging."""
        if not self.state.debug_input_enabled:
            return

        self.state.debug_input_events.append(self._debug_event_status(event))

        if len(self.state.debug_input_events) > 100:
            self.state.debug_input_events = self.state.debug_input_events[-100:]

    def _pan_direction_from_key(self, key: str) -> str | None:
        """Map vim-style movement keys to pan directions."""
        key_map = {
            "h": "left",
            "l": "right",
            "k": "up",
            "j": "down",
        }
        return key_map.get(key)

    def _render_app_for(self, scene: Scene) -> TerminalRenderApp:
        """Return a render app updated for the current scene and viewport."""
        if self.render_app is None:
            self.render_app = TerminalRenderApp(
                scene=scene,
                viewport=self.viewport,
                capabilities=self.capabilities,
            )
            return self.render_app

        if (
            self.render_app.last_width != self.viewport.view_width
            or self.render_app.last_height != self.viewport.view_height
        ):
            self.render_app = TerminalRenderApp(
                scene=scene,
                viewport=self.viewport,
                capabilities=self.capabilities,
            )
            return self.render_app

        self.render_app.scene = scene
        self.render_app.viewport = self.viewport
        self.render_app.renderer.viewport = self.viewport
        return self.render_app

    def _pan_with_key(self, key: str) -> None:
        world_width = self.viewport.world_max_x - self.viewport.world_min_x
        world_height = self.viewport.world_max_y - self.viewport.world_min_y
        dx = world_width / self.viewport.view_width
        dy = world_height / self.viewport.view_height

        if key == "left":
            self.viewport = self.viewport.pan(-dx, 0.0)
        elif key == "right":
            self.viewport = self.viewport.pan(dx, 0.0)
        elif key == "up":
            self.viewport = self.viewport.pan(0.0, dy)
        elif key == "down":
            self.viewport = self.viewport.pan(0.0, -dy)

        self.state.status_message = f"Panned {key}"

    def _zoom_at_view_center(self, factor: float) -> None:
        center_x = (self.viewport.world_min_x + self.viewport.world_max_x) / 2
        center_y = (self.viewport.world_min_y + self.viewport.world_max_y) / 2
        self.viewport = self.viewport.zoom(factor, center_x, center_y)
        self.state.status_message = self._zoom_status(factor)

    def _zoom_at_screen(self, x: int, y: int, factor: float) -> None:
        world_point = self.viewport.view_to_world(x, y)
        self.viewport = self.viewport.zoom(factor, world_point.x, world_point.y)
        self.state.status_message = self._zoom_status(factor)

    def _update_mouse_drag_state(self, x: int, y: int) -> None:
        """Mark the current gesture as a drag once it moves far enough."""
        if self.mouse_press_screen is None:
            return

        press_x, press_y = self.mouse_press_screen
        distance_sq = (x - press_x) ** 2 + (y - press_y) ** 2
        threshold_sq = self.CLICK_DRAG_THRESHOLD_CELLS ** 2

        if distance_sq > threshold_sq:
            self.mouse_dragging = True

    def _is_click_release(self, x: int, y: int) -> bool:
        """Return True when a release should count as a feature-selection click."""
        if self.mouse_press_screen is None:
            return False

        if self.mouse_dragging:
            return False

        press_x, press_y = self.mouse_press_screen
        distance_sq = (x - press_x) ** 2 + (y - press_y) ** 2
        threshold_sq = self.CLICK_DRAG_THRESHOLD_CELLS ** 2
        return distance_sq <= threshold_sq

    def _clear_mouse_drag_state(self) -> None:
        """Clear press/drag tracking."""
        self.mouse_press_screen = None
        self.last_mouse_screen = None
        self.mouse_dragging = False

    def _begin_pending_click(self, x: int, y: int) -> None:
        """Remember a possible feature-selection click."""
        self.pending_click_screen = (x, y)
        self.pending_click_started_at = time.monotonic()
        self.pending_click_previous_selection = (
            self.state.selected_feature,
            self.state.status_message,
        )
        self.pending_click_committed = False

    def commit_pending_click_if_ready(self, now: float | None = None) -> bool:
        """Commit a possible click if no release event arrives soon."""
        if self.pending_click_screen is None:
            return False

        if self.mouse_dragging:
            return False

        if self.pending_click_committed:
            return False

        if self.pending_click_started_at is None:
            return False

        if now is None:
            now = time.monotonic()

        elapsed = now - self.pending_click_started_at
        if elapsed < self.PENDING_CLICK_SECONDS:
            return False

        x, y = self.pending_click_screen
        self._commit_click_selection(x, y)
        self.pending_click_committed = True
        return True

    def _commit_click_selection(self, x: int, y: int) -> None:
        """Select the closest visible feature near a screen click."""
        self._query_at_screen(x, y)

    def _cancel_pending_click(self, restore_committed: bool) -> None:
        """Cancel a possible click after the gesture becomes a drag."""
        if (
            restore_committed
            and self.pending_click_committed
            and self.pending_click_previous_selection is not None
        ):
            selected_feature, status_message = self.pending_click_previous_selection
            self.state.selected_feature = selected_feature
            self.state.status_message = status_message

        self._clear_pending_click()

    def _clear_pending_click(self) -> None:
        """Forget pending click state."""
        self.pending_click_screen = None
        self.pending_click_started_at = None
        self.pending_click_previous_selection = None
        self.pending_click_committed = False

    def _pan_with_mouse_drag(self, x: int, y: int) -> None:
        if self.last_mouse_screen is None:
            self.last_mouse_screen = (x, y)
            return

        last_x, last_y = self.last_mouse_screen
        previous_world = self.viewport.view_to_world(last_x, last_y)
        current_world = self.viewport.view_to_world(x, y)
        self.viewport = self.viewport.pan(
            previous_world.x - current_world.x,
            previous_world.y - current_world.y,
        )
        self.last_mouse_screen = (x, y)
        self.state.status_message = "Mouse pan"

    def _query_at_screen(self, x: int, y: int) -> None:
        nearest_feature = self._nearest_visible_feature_query(x, y)

        if nearest_feature is None:
            self.state.selected_feature = "No selectable visible feature near click."
            self.state.status_message = self.state.selected_feature
            return

        distance_sq, feature_text = nearest_feature
        threshold_sq = self.SELECTION_MAX_DISTANCE_CELLS ** 2

        if distance_sq > threshold_sq:
            self.state.selected_feature = "No selectable visible feature near click."
            self.state.status_message = self.state.selected_feature
            return

        self.state.selected_feature = feature_text
        self.state.status_message = self.state.selected_feature.replace(" | ", ", ")

    def _nearest_visible_feature_query(self, x: int, y: int) -> tuple[float, str] | None:
        """Return the nearest selectable feature from currently visible layers."""
        candidates = []

        if self.state.show_points:
            point_result = self._nearest_point_query(x, y)
            if point_result is not None:
                candidates.append(point_result)

        if self.state.show_grid:
            grid_result = self._nearest_grid_query(x, y)
            if grid_result is not None:
                candidates.append(grid_result)

        if self.state.show_tin:
            tin_edge_result = self._nearest_tin_edge_query(x, y)
            if tin_edge_result is not None:
                candidates.append(tin_edge_result)

        if not candidates:
            return None

        return min(candidates, key=lambda item: item[0])

    def _nearest_point_query(self, x: int, y: int) -> tuple[float, str] | None:
        nearest = None

        for point in self.project_state.points:
            cell_x, cell_y = self._world_to_cell(point.x, point.y)
            distance_sq = (cell_x - x) ** 2 + (cell_y - y) ** 2

            if nearest is None or distance_sq < nearest[0]:
                feature_text = (
                    "Point"
                    f" | id={point.id}"
                    f" | name={point.name}"
                    f" | x={point.x:.2f}"
                    f" | y={point.y:.2f}"
                    f" | z={point.z:.2f}"
                )
                nearest = (distance_sq, feature_text)

        return nearest

    def _nearest_grid_query(self, x: int, y: int) -> tuple[float, str] | None:
        nearest = None
        grid = self.project_state.idw_grid

        for row in range(grid.y_divisions + 1):
            for col in range(grid.x_divisions + 1):
                grid_x, grid_y, grid_z = grid.grid_intersection(row, col)
                cell_x, cell_y = self._world_to_cell(grid_x, grid_y)
                distance_sq = (cell_x - x) ** 2 + (cell_y - y) ** 2

                if nearest is None or distance_sq < nearest[0]:
                    feature_text = (
                        "Grid node"
                        f" | row={row}"
                        f" | col={col}"
                        f" | x={grid_x:.2f}"
                        f" | y={grid_y:.2f}"
                        f" | z={grid_z:.2f}"
                    )
                    nearest = (distance_sq, feature_text)

        return nearest

    def _nearest_tin_edge_query(self, x: int, y: int) -> tuple[float, str] | None:
        nearest = None
        vertex_by_id = self.project_state.tin.vertex_by_id()

        for start_id, end_id in self.project_state.tin.unique_edge_keys():
            start = vertex_by_id[start_id]
            end = vertex_by_id[end_id]
            start_cell_x, start_cell_y = self._world_to_cell(start.x, start.y)
            end_cell_x, end_cell_y = self._world_to_cell(end.x, end.y)
            distance_sq = self._point_to_segment_distance_sq(
                x,
                y,
                start_cell_x,
                start_cell_y,
                end_cell_x,
                end_cell_y,
            )

            if nearest is None or distance_sq < nearest[0]:
                length = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5
                feature_text = (
                    "TIN arc"
                    f" | start_vertex={start.id}"
                    f" | end_vertex={end.id}"
                    f" | start_z={start.z:.2f}"
                    f" | end_z={end.z:.2f}"
                    f" | length={length:.2f}"
                )
                nearest = (distance_sq, feature_text)

        return nearest

    def _world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        """Convert world coordinates to the terminal cell used for hit testing."""
        view_point = self.viewport.world_to_view(x, y)
        return (
            self._view_coordinate_to_cell(view_point.x, self.viewport.view_width),
            self._view_coordinate_to_cell(view_point.y, self.viewport.view_height),
        )

    def _view_coordinate_to_cell(self, value: float, size: int) -> int:
        """Convert one view coordinate to a valid rendered cell index."""
        cell = round(value)

        if 0 <= value <= size:
            return max(0, min(size - 1, cell))

        return cell

    def _point_to_segment_distance_sq(
        self,
        px: float,
        py: float,
        ax: float,
        ay: float,
        bx: float,
        by: float,
    ) -> float:
        segment_dx = bx - ax
        segment_dy = by - ay
        segment_length_sq = segment_dx * segment_dx + segment_dy * segment_dy

        if segment_length_sq == 0:
            return (px - ax) ** 2 + (py - ay) ** 2

        t = (
            (px - ax) * segment_dx
            + (py - ay) * segment_dy
        ) / segment_length_sq
        t = max(0.0, min(1.0, t))
        closest_x = ax + t * segment_dx
        closest_y = ay + t * segment_dy
        return (px - closest_x) ** 2 + (py - closest_y) ** 2

    def _zoom_status(self, factor: float) -> str:
        if factor > 1:
            return "Zoomed in"

        return "Zoomed out"
    
    def process_support_commands(self) -> bool:
        """Process all queued support-panel commands."""
        if self.command_queue is None:
            return False

        processed_command = False
        
        while True:
            try:
                request = self.command_queue.get_nowait()
            except Empty:
                return processed_command
            
            response = self.handle_support_command(request.text)
            request.reply_queue.put(response)
            processed_command = True

    def handle_support_command(self, command: str) -> str:
        """Handle one text command from the support panel."""
        stripped_command = command.strip()
        parts = stripped_command.lower().split()

        if not parts:
            return "ERROR: empty command"

        if parts == ["mode"]:
            return f"OK: mode={self.state.interaction_mode}"

        if parts == ["mode", "info"]:
            self.state.interaction_mode = "info"
            self.state.status_message = "Info mode"
            return "OK: mode=info"

        if parts == ["mode", "normal"]:
            self.state.interaction_mode = "normal"
            self.state.status_message = "Normal mode"
            return "OK: mode=normal"

        if parts == ["selected", "feature"]:
            return f"OK: {self.state.selected_feature}"

        if parts == ["layers", "summary"]:
            return (
                "OK: "
                f"points={'on' if self.state.show_points else 'off'} "
                f"grid={'on' if self.state.show_grid else 'off'} "
                f"tin={'on' if self.state.show_tin else 'off'} "
                f"contours={'on' if self.state.show_contours else 'off'} "
                f"contour_labels="
                f"{'on' if self.state.show_contour_labels else 'off'} "
                f"contour_source={self.state.contour_source} "
                f"contour_interval={self.state.contour_interval:g}"
            )
        
        if parts == ["show", "grid"]:
            self.state.show_grid = True
            self.state.status_message = "Grid visible"
            return f"OK: {self.state.status_message}"
        
        if parts == ["hide", "grid"]:
            self.state.show_grid = False
            self.state.status_message = "Grid hidden"
            return f"OK: {self.state.status_message}"
        
        if parts == ["toggle", "grid"]:
            self.state.show_grid = not self.state.show_grid
            self.state.status_message = self._visibility_status(
                "Grid",
                self.state.show_grid,
            )
            return f"OK: {self.state.status_message}"
        
        if parts == ["show", "tin"]:
            self.state.show_tin = True
            self.state.status_message = "TIN visible"
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "tin"]:
            self.state.show_tin = False
            self.state.status_message = "TIN hidden"
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "tin"]:
            self.state.show_tin = not self.state.show_tin
            self.state.status_message = self._visibility_status(
                "TIN",
                self.state.show_tin,
            )
            return f"OK: {self.state.status_message}"
        
        if parts == ["show", "points"]:
            self.state.show_points = True
            self.state.status_message = "Points visible"
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "points"]:
            self.state.show_points = False
            self.state.status_message = "Points hidden"
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "points"]:
            self.state.show_points = not self.state.show_points
            self.state.status_message = self._visibility_status(
                "Points",
                self.state.show_points,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "contours"]:
            self.state.show_contours = True
            self.state.status_message = "Contours visible"
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "contours"]:
            self.state.show_contours = False
            self.state.status_message = "Contours hidden"
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "contours"]:
            self.state.show_contours = not self.state.show_contours
            self.state.status_message = self._visibility_status(
                "Contours",
                self.state.show_contours,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "contour", "labels"]:
            self.state.show_contour_labels = True
            self.state.status_message = "Contour labels visible"
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "contour", "labels"]:
            self.state.show_contour_labels = False
            self.state.status_message = "Contour labels hidden"
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "contour", "labels"]:
            self.state.show_contour_labels = not self.state.show_contour_labels
            self.state.status_message = self._visibility_status(
                "Contour labels",
                self.state.show_contour_labels,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "contour", "source"]:
            self._toggle_contour_source()
            return f"OK: {self.state.status_message}"

        if len(parts) == 3 and parts[:2] == ["contour", "source"]:
            return self._set_contour_source(parts[2])

        if len(parts) == 4 and parts[:3] == ["set", "contour", "source"]:
            return self._set_contour_source(parts[3])

        if len(parts) == 3 and parts[:2] == ["contour", "interval"]:
            return self._set_contour_interval(parts[2])

        if len(parts) == 4 and parts[:3] == ["set", "contour", "interval"]:
            return self._set_contour_interval(parts[3])

        if parts == ["contour", "summary"]:
            return self.contour_summary()

        if parts in (
            ["config"],
            ["current", "config"],
            ["get", "current", "config"],
        ):
            return f"OK: {self.project_state.config.summary()}"

        if parts in (
            ["model", "summary"],
            ["get", "model", "summary"],
        ):
            return self.model_summary()

        if len(parts) == 4 and parts[:2] == ["set", "grid"]:
            return self._set_grid_divisions(parts[2], parts[3])

        if len(parts) == 5 and parts[:3] == ["set", "grid", "divisions"]:
            return self._set_grid_divisions(parts[3], parts[4])

        if len(parts) == 4 and parts[:2] == ["grid", "divisions"]:
            return self._set_grid_divisions(parts[2], parts[3])

        if parts == ["reload", "dataset"]:
            return self._reload_dataset()

        if len(parts) >= 3 and parts[:2] == ["load", "dataset"]:
            path_text = stripped_command.split(maxsplit=2)[2]
            return self._load_dataset(path_text)

        if parts == ["reset"]:
            self.viewport = self.initial_viewport
            self.state.status_message = "Viewport reset"
            return f"OK: {self.state.status_message}"
        
        if parts == ["summary"]:
            return self.model_summary()

        if parts == ["debug", "input", "start"]:
            self.state.debug_input_enabled = True
            self.state.debug_input_events.clear()
            self.state.status_message = "Input debug enabled"
            return "OK: input debug enabled"

        if parts == ["debug", "input", "poll"]:
            if not self.state.debug_input_enabled:
                return "ERROR: input debug is not enabled"

            if not self.state.debug_input_events:
                return "OK: no input"

            event_text = self.state.debug_input_events.pop(0)
            return f"OK: input {event_text}"

        if parts == ["debug", "input", "stop"]:
            self.state.debug_input_enabled = False
            self.state.debug_input_events.clear()
            self.state.status_message = "Input debug disabled"
            return "OK: input debug disabled"
        
        if len(parts) == 4 and parts[:2] == ["query", "grid"]:
            try:
                row = int(parts[2])
                col = int(parts[3])
            except ValueError:
                return "ERROR: row and col must be integers"
            
            try:
                x, y, z = self.project_state.idw_grid.grid_intersection(row, col)
            except ValueError as error:
                return f"ERROR: {error}"
            
            self.state.status_message = (
                f"Grid row={row}, col={col}, z={z:.3f}"
            )
            return (
                f"OK: grid intersection row={row}, col={col}, "
                f"x={x:.3f}, y={y:.3f}, z={z:.3f}"
        )

        if parts == ["quit", "viewer"]:
            self.state.running = False
            return "OK: viewer quitting"

        return f"ERROR: unknown command: {command}"
    
    def model_summary(self) -> str:
        """Return a short model summary."""
        return (
            "OK: "
            f"points={len(self.project_state.points)}, "
            f"grid={self.project_state.idw_grid.x_divisions}x"
            f"{self.project_state.idw_grid.y_divisions}, "
            f"tin_vertices={len(self.project_state.tin.vertices)}, "
            f"tin_triangles={len(self.project_state.tin.triangles)}, "
            f"dataset={self.project_state.config.dataset_path}, "
            f"interpolation={self.project_state.config.interpolation_method}"
        )

    def contour_summary(self) -> str:
        """Return a short contour summary for the current contour settings."""
        polylines = self.contour_polylines()
        open_count = sum(1 for polyline in polylines if not polyline.closed)
        closed_count = sum(1 for polyline in polylines if polyline.closed)

        if self.state.contour_source == "tin":
            value_min, value_max = tin_value_range(self.project_state.tin)
        else:
            value_min, value_max = grid_value_range(self.project_state.idw_grid)

        levels = generate_contour_levels(
            value_min,
            value_max,
            self.state.contour_interval,
        )
        return (
            "OK: "
            f"source={self.state.contour_source}, "
            f"interval={self.state.contour_interval:g}, "
            f"levels={len(levels)}, "
            f"polylines={len(polylines)}, "
            f"open={open_count}, "
            f"closed={closed_count}"
        )

    def _set_contour_source(self, source: str) -> str:
        """Set contour generation source from a support command."""
        if source not in ("grid", "tin"):
            return "ERROR: contour source must be grid or tin"

        self.state.contour_source = source
        self._update_project_config(contour_source=source)
        self.state.status_message = f"Contour source: {source}"
        return f"OK: {self.state.status_message}"

    def _set_contour_interval(self, value_text: str) -> str:
        """Set contour interval from a support command."""
        try:
            interval = float(value_text)
        except ValueError:
            return "ERROR: contour interval must be a number"

        if interval <= 0:
            return "ERROR: contour interval must be positive"

        self.state.contour_interval = interval
        self._update_project_config(contour_interval=interval)
        self.state.status_message = f"Contour interval: {interval:g}"
        return f"OK: {self.state.status_message}"

    def _set_grid_divisions(self, x_text: str, y_text: str) -> str:
        """Set grid divisions and rebuild the project safely."""
        try:
            x_divisions = int(x_text)
            y_divisions = int(y_text)
        except ValueError:
            return "ERROR: grid divisions must be integers"

        try:
            config = replace(
                self.project_state.config,
                grid_x_divisions=x_divisions,
                grid_y_divisions=y_divisions,
                contour_source=self.state.contour_source,
                contour_interval=self.state.contour_interval,
            )
        except ValueError as error:
            return f"ERROR: {error}"

        self.state.status_message = f"Rebuilding grid {x_divisions}x{y_divisions}..."
        return self._rebuild_project(
            config,
            reset_viewport=False,
            success_message=f"Grid divisions set to {x_divisions}x{y_divisions}",
            failure_prefix="grid rebuild failed",
        )

    def _load_dataset(self, path_text: str) -> str:
        """Load a new dataset without discarding the current project on error."""
        path_text = path_text.strip()
        if not path_text:
            return "ERROR: dataset path is required"

        try:
            config = replace(
                self.project_state.config,
                dataset_path=Path(path_text),
                contour_source=self.state.contour_source,
                contour_interval=self.state.contour_interval,
            )
        except ValueError as error:
            return f"ERROR: {error}"

        self.state.status_message = f"Loading dataset {config.dataset_path}..."
        return self._rebuild_project(
            config,
            reset_viewport=True,
            success_message=f"Dataset loaded: {config.dataset_path}",
            failure_prefix="dataset load failed",
        )

    def _reload_dataset(self) -> str:
        """Reload the current dataset through the normal project build path."""
        config = replace(
            self.project_state.config,
            contour_source=self.state.contour_source,
            contour_interval=self.state.contour_interval,
        )
        self.state.status_message = f"Reloading dataset {config.dataset_path}..."
        return self._rebuild_project(
            config,
            reset_viewport=False,
            success_message=f"Dataset reloaded: {config.dataset_path}",
            failure_prefix="dataset reload failed",
        )

    def _rebuild_project(
        self,
        config: ProjectConfig,
        reset_viewport: bool,
        success_message: str,
        failure_prefix: str,
    ) -> str:
        """Rebuild and swap project state only after a successful build."""
        previous_state = self.project_state
        result = try_rebuild_project_state(previous_state, config)

        if not result.success:
            self.project_state = previous_state
            self.state.status_message = f"ERROR: {failure_prefix}: {result.message}"
            return self.state.status_message

        self._replace_project_state(result.project_state, reset_viewport)
        self.state.status_message = success_message
        return f"OK: {success_message}"

    def _replace_project_state(
        self,
        project_state: ProjectState,
        reset_viewport: bool,
    ) -> None:
        """Swap in a freshly built project and invalidate cached render models."""
        self.project_state = project_state
        self.state.contour_source = project_state.config.contour_source
        self.state.contour_interval = project_state.config.contour_interval

        if reset_viewport:
            self.viewport = initial_viewport_from_points(
                project_state.points,
                view_width=self.viewport.view_width,
                view_height=self.viewport.view_height,
                padding=0.05,
            )
            self.initial_viewport = self.viewport

        self._clear_model_caches()

    def _clear_model_caches(self) -> None:
        """Clear cached render and contour data after project model changes."""
        self.scene_cache_key = None
        self.scene_cache = None
        self.contour_cache_key = None
        self.contour_cache = None
        self._frame_dirty = True

    def _update_project_config(self, **changes) -> None:
        """Update persisted config for settings that do not require a rebuild."""
        self.project_state.config = replace(self.project_state.config, **changes)
