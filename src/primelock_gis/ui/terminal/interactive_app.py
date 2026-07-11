"""Interactive terminal app set-up."""

import shutil
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
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
    terrain_to_scene,
    tin_to_scene,
)
from primelock_gis.core.rendering.symbology import (
    PointStyle,
    PolylineStyle,
    TerrainStyle,
)
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.i18n import Language, get_language, normalize_language, tr
from primelock_gis.ui.terminal.backends.base import TerminalBackendError
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.ui.terminal.events import (
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    TerminalEvent,
)
from primelock_gis.ui.terminal.render_app import TerminalRenderApp
from primelock_gis.ui.terminal.screen import clear_screen, present_frame
from primelock_gis.ui.terminal.session import TerminalSession
from primelock_gis.ui.terminal.support_panel import CommandRequest
from primelock_gis.ui.terminal.theme import TERMINAL_THEME, status_color

TERRAIN_PALETTES = {
    "elevation": (
        TERMINAL_THEME.terrain_low,
        TERMINAL_THEME.terrain_low_mid,
        TERMINAL_THEME.terrain_high_mid,
        TERMINAL_THEME.terrain_high,
    ),
    "grayscale": (
        "#111827",
        "#4B5563",
        "#9CA3AF",
        "#F9FAFB",
    ),
    "heat": (
        "#172554",
        "#0891B2",
        "#F59E0B",
        "#B91C1C",
    ),
}
TERRAIN_PALETTE_ALIASES = {
    "gray": "grayscale",
    "grey": "grayscale",
    "greyscale": "grayscale",
}
TERRAIN_PALETTE_NAMES = tuple(TERRAIN_PALETTES)


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
        if isinstance(event, ResizeEvent):
            flush_pending_mouse_motion()
            if coalesced and isinstance(coalesced[-1], ResizeEvent):
                coalesced[-1] = event
            else:
                coalesced.append(event)
            continue

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
    show_terrain: bool = False
    show_grid: bool = False
    show_tin: bool = True
    show_contours: bool = False
    show_contour_labels: bool = False
    contour_source: str = "grid"
    contour_interval: float = 50.0
    terrain_opacity: float = 1.0
    terrain_palette: str = "elevation"
    selected_feature: str = "No feature selected."
    status_message: str = "Ready"
    terminal_warning: str | None = None


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
        language: Language | str | None = None,
    ) -> None:
        self.project_state = project_state
        self.viewport = viewport
        self.initial_viewport = viewport
        self.capabilities = capabilities
        self.command_queue = command_queue
        self.language = normalize_language(
            language if language is not None else get_language()
        )
        self.state = InteractiveState()
        self.state.selected_feature = self._text(
            "viewer.feature.none",
            "No feature selected.",
            "未选择任何要素。",
        )
        self.state.status_message = self._text("common.ready", "Ready", "就绪")
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
        self.scene_cache_key: (
            tuple[
                bool,
                bool,
                bool,
                bool,
                bool,
                bool,
                str,
                float,
                float,
                str,
            ]
            | None
        ) = None
        self.scene_cache: Scene | None = None
        self.contour_cache_key: tuple[str, float] | None = None
        self.contour_cache: list[ContourPolyline] | None = None
        self._frame_dirty = True
        self._screen_needs_clear = True
        self._terminal_lines = viewport.view_height + self.STATUS_ROWS

    def _text(self, message_key: str, english: str, chinese: str, **values) -> str:
        """Return one localized viewer message."""
        default = chinese if self.language == "zh-CN" else english
        return tr(message_key, language=self.language, default=default, **values)

    def build_scene(self) -> Scene:
        """Build the currently visible scene from enabled layers."""
        cache_key = self._scene_visibility_cache_key()
        if self.scene_cache_key == cache_key and self.scene_cache is not None:
            return self.scene_cache

        scene = Scene()

        if self.state.show_terrain:
            terrain_surface = self._terrain_surface()
            terrain_scene = terrain_to_scene(
                terrain_surface,
                style=self._terrain_style(),
                source=self.state.contour_source,
            )
            self._merge_scene(scene, terrain_scene)

        if self.state.show_grid:
            grid_scene = grid_to_scene(
                self.project_state.grid,
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
                "grid",
                self.state.show_grid,
            )
            return

        if key == "b":
            self.state.show_terrain = not self.state.show_terrain
            self.state.status_message = self._visibility_status(
                "terrain",
                self.state.show_terrain,
            )
            return

        if key == "t":
            self.state.show_tin = not self.state.show_tin
            self.state.status_message = self._visibility_status(
                "tin",
                self.state.show_tin,
            )
            return

        if key == "p":
            self.state.show_points = not self.state.show_points
            self.state.status_message = self._visibility_status(
                "points",
                self.state.show_points,
            )
            return

        if key == "c":
            self.state.show_contours = not self.state.show_contours
            self.state.status_message = self._visibility_status(
                "contours",
                self.state.show_contours,
            )
            return

        if key == "m":
            self._toggle_contour_source()
            return

        if key == "v":
            self.state.show_contour_labels = not self.state.show_contour_labels
            self.state.status_message = self._visibility_status(
                "contour_labels",
                self.state.show_contour_labels,
            )
            return

        if key == "r":
            self.viewport = self.initial_viewport
            self.state.status_message = self._text(
                "viewer.viewport.reset", "Viewport reset", "视图已重置"
            )
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

        self.state.status_message = self._text(
            "viewer.key.unknown",
            "Unknown key: {key}",
            "未知按键：{key}",
            key=repr(key),
        )

    def handle_event(self, event: TerminalEvent) -> None:
        """Handle one terminal input event."""
        if isinstance(event, ResizeEvent):
            self._resize_to(event.width, event.height)
            return

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
        return self._resize_to(terminal_size.columns, terminal_size.lines)

    def _resize_to(self, width: int, terminal_lines: int) -> int:
        """Resize from full terminal dimensions and return the final status row."""
        width = max(1, width)
        terminal_lines = max(self.STATUS_ROWS + 1, terminal_lines)
        height = max(1, terminal_lines - self.STATUS_ROWS)
        self._terminal_lines = terminal_lines

        if width != self.viewport.view_width or height != self.viewport.view_height:
            self.viewport = self.viewport.resize_viewport(width, height)
            self.initial_viewport = self.initial_viewport.resize_viewport(width, height)
            self.state.status_message = self._text(
                "viewer.resized",
                "Resized to {width}x{height}",
                "终端尺寸已调整为 {width}x{height}",
                width=width,
                height=height,
            )
            self._frame_dirty = True
            self._screen_needs_clear = True

        return self._terminal_lines

    def run(self) -> None:
        """Run the interactive terminal application loop."""
        try:
            with TerminalSession() as terminal:
                if terminal.diagnostic:
                    self.state.terminal_warning = terminal.diagnostic
                clear_screen()
                self._screen_needs_clear = False

                while self.state.running:
                    if self.commit_pending_click_if_ready():
                        self._frame_dirty = True

                    if self.process_support_commands():
                        self._frame_dirty = True

                    self.resize_if_needed()
                    events = self._read_ready_events(
                        terminal,
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
                            instruction_row=max(1, self._terminal_lines - 1),
                            info_row=self._terminal_lines,
                            width=self.viewport.view_width,
                            instruction_color=TERMINAL_THEME.muted,
                            info_color=status_color(self.status_info_text()),
                            capabilities=self.capabilities,
                        )
                        self._frame_dirty = False
        except KeyboardInterrupt:
            self.state.running = False
        except TerminalBackendError as error:
            self.state.running = False
            print(
                self._text(
                    "viewer.terminal.error",
                    "ERROR: {error}",
                    "错误：{error}",
                    error=error,
                ),
                file=sys.stderr,
            )

    def _read_ready_events(
        self,
        terminal: TerminalSession,
        timeout: float,
    ) -> list[TerminalEvent]:
        """Read the currently available terminal events without leaving a backlog."""
        first_event = terminal.read_event(timeout=timeout)
        if first_event is None:
            return []

        events = [first_event]

        while True:
            event = terminal.read_event(timeout=0.0)
            if event is None:
                break

            events.append(event)

        return events

    def status_instruction_text(self) -> str:
        """Return the controls row for the bottom status area."""
        terrain = self._visibility_label(self.state.show_terrain)
        grid = self._visibility_label(self.state.show_grid)
        tin = self._visibility_label(self.state.show_tin)
        points = self._visibility_label(self.state.show_points)
        contours = self._visibility_label(self.state.show_contours)
        return self._text(
            "viewer.controls",
            "q quit | b terrain | g grid | t TIN | p points | c contours | m source | "
            "v labels | r reset | hjkl pan | +/- zoom | terrain={terrain} | grid={grid} "
            "| tin={tin} | points={points} | contours={contours} | source={source} "
            "| interval={interval:g} | terrain_opacity={opacity:.0%} "
            "| terrain_palette={palette} | grid={grid_x}x{grid_y}",
            "q 退出 | b 地形 | g 网格 | t TIN | p 点 | c 等高线 | m 数据源 | "
            "v 标注 | r 重置 | hjkl 平移 | +/- 缩放 | 地形={terrain} | 网格={grid} "
            "| TIN={tin} | 点={points} | 等高线={contours} | 数据源={source} "
            "| 等高距={interval:g} | 地形不透明度={opacity:.0%} "
            "| 地形色带={palette} | 网格={grid_x}x{grid_y}",
            terrain=terrain,
            grid=grid,
            tin=tin,
            points=points,
            contours=contours,
            source=self._source_label(self.state.contour_source),
            interval=self.state.contour_interval,
            opacity=self.state.terrain_opacity,
            palette=self._palette_label(self.state.terrain_palette),
            grid_x=self.project_state.config.grid_x_divisions,
            grid_y=self.project_state.config.grid_y_divisions,
        )

    def _visibility_label(self, visible: bool) -> str | bool:
        """Return a localized visibility state without changing English output."""
        if self.language == "zh-CN":
            return "开" if visible else "关"
        return visible

    def status_info_text(self) -> str:
        """Return the information row for the bottom status area."""
        if self.state.terminal_warning:
            return self._text(
                "viewer.warning",
                "WARN: {warning} | {status}",
                "警告：{warning} | {status}",
                warning=self.state.terminal_warning,
                status=self.state.status_message,
            )
        return self.state.status_message

    def _merge_scene(self, target: Scene, source: Scene) -> None:
        """Merge one scene into another scene."""
        target.terrains.extend(source.terrains)
        target.polylines.extend(source.polylines)
        target.points.extend(source.points)
        target.texts.extend(source.texts)

    def _scene_visibility_cache_key(
        self,
    ) -> tuple[bool, bool, bool, bool, bool, bool, str, float, float, str]:
        """Return the state values that affect the static rendered scene."""
        return (
            self.state.show_terrain,
            self.state.show_grid,
            self.state.show_tin,
            self.state.show_points,
            self.state.show_contours,
            self.state.show_contour_labels,
            self.state.contour_source,
            self.state.contour_interval,
            self.state.terrain_opacity,
            self.state.terrain_palette,
        )

    def _terrain_surface(self):
        """Return the model used for terrain colour sampling."""
        if self.state.contour_source == "tin":
            return self.project_state.tin

        return self.project_state.grid

    def _terrain_style(self) -> TerrainStyle:
        """Return the current terrain colour style."""
        low, low_mid, high_mid, high = TERRAIN_PALETTES[self.state.terrain_palette]
        return TerrainStyle(
            low_color=low,
            low_mid_color=low_mid,
            high_mid_color=high_mid,
            high_color=high,
            opacity=self.state.terrain_opacity,
            background_color=TERMINAL_THEME.background,
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
            value_min, value_max = grid_value_range(self.project_state.grid)
            levels = generate_contour_levels(
                value_min,
                value_max,
                self.state.contour_interval,
            )
            segments = contour_segments_from_grid(
                self.project_state.grid,
                levels,
                self.state.contour_interval,
            )
            polylines = trace_contour_segments(
                segments,
                self.project_state.grid,
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
        self.state.status_message = self._text(
            "viewer.contour.source",
            "Contour source: {source}",
            "等高线数据源：{source}",
            source=self._source_label(self.state.contour_source),
        )

    def _visibility_status(self, layer_name: str, visible: bool) -> str:
        """Return a short visibility status message."""
        label = self._layer_label(layer_name)
        if visible:
            return self._text(
                "viewer.layer.visible",
                "{layer} visible",
                "{layer}已显示",
                layer=label,
            )

        return self._text(
            "viewer.layer.hidden", "{layer} hidden", "{layer}已隐藏", layer=label
        )

    def _layer_label(self, layer_name: str) -> str:
        labels = {
            "terrain": ("Terrain", "地形"),
            "grid": ("Grid", "网格"),
            "tin": ("TIN", "TIN"),
            "points": ("Points", "点图层"),
            "contours": ("Contours", "等高线"),
            "contour_labels": ("Contour labels", "等高线标注"),
        }
        english, chinese = labels.get(layer_name, (layer_name, layer_name))
        return chinese if self.language == "zh-CN" else english

    def _source_label(self, source: str) -> str:
        if self.language != "zh-CN":
            return source
        return {"grid": "网格", "tin": "TIN"}.get(source, source)

    def _palette_label(self, palette: str) -> str:
        if self.language != "zh-CN":
            return palette
        return {
            "elevation": "高程",
            "grayscale": "灰度",
            "heat": "热力",
        }.get(palette, palette)

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

        direction = {
            "left": "左",
            "right": "右",
            "up": "上",
            "down": "下",
        }.get(key, key)
        self.state.status_message = self._text(
            "viewer.panned",
            "Panned {direction}",
            "视图已向{direction}平移",
            direction=direction if self.language == "zh-CN" else key,
        )

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
        threshold_sq = self.CLICK_DRAG_THRESHOLD_CELLS**2

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
        threshold_sq = self.CLICK_DRAG_THRESHOLD_CELLS**2
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
        self.state.status_message = self._text(
            "viewer.mouse.pan", "Mouse pan", "鼠标拖动平移"
        )

    def _query_at_screen(self, x: int, y: int) -> None:
        nearest_feature = self._nearest_visible_feature_query(x, y)

        if nearest_feature is None:
            self.state.selected_feature = self._text(
                "viewer.feature.not_found",
                "No selectable visible feature near click.",
                "单击位置附近没有可选择的可见要素。",
            )
            self.state.status_message = self.state.selected_feature
            return

        distance_sq, feature_text = nearest_feature
        threshold_sq = self.SELECTION_MAX_DISTANCE_CELLS**2

        if distance_sq > threshold_sq:
            self.state.selected_feature = self._text(
                "viewer.feature.not_found",
                "No selectable visible feature near click.",
                "单击位置附近没有可选择的可见要素。",
            )
            self.state.status_message = self.state.selected_feature
            return

        self.state.selected_feature = feature_text
        self.state.status_message = self.state.selected_feature.replace(" | ", ", ")

    def _nearest_visible_feature_query(
        self, x: int, y: int
    ) -> tuple[float, str] | None:
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
                    self._text("viewer.feature.point", "Point", "点要素")
                    + f" | {self._text('viewer.field.id', 'id', '编号')}={point.id}"
                    f" | {self._text('viewer.field.name', 'name', '名称')}={point.name}"
                    f" | x={point.x:.2f}"
                    f" | y={point.y:.2f}"
                    f" | z={point.z:.2f}"
                )
                nearest = (distance_sq, feature_text)

        return nearest

    def _nearest_grid_query(self, x: int, y: int) -> tuple[float, str] | None:
        nearest = None
        grid = self.project_state.grid

        for row in range(grid.y_divisions + 1):
            for col in range(grid.x_divisions + 1):
                grid_x, grid_y, grid_z = grid.grid_intersection(row, col)
                cell_x, cell_y = self._world_to_cell(grid_x, grid_y)
                distance_sq = (cell_x - x) ** 2 + (cell_y - y) ** 2

                if nearest is None or distance_sq < nearest[0]:
                    feature_text = (
                        self._text("viewer.feature.grid_node", "Grid node", "网格节点")
                        + f" | {self._text('viewer.field.row', 'row', '行')}={row}"
                        f" | {self._text('viewer.field.col', 'col', '列')}={col}"
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
                    self._text("viewer.feature.tin_edge", "TIN arc", "TIN 边")
                    + f" | {self._text('viewer.field.start_vertex', 'start_vertex', '起点')}={start.id}"
                    f" | {self._text('viewer.field.end_vertex', 'end_vertex', '终点')}={end.id}"
                    f" | {self._text('viewer.field.start_z', 'start_z', '起点高程')}={start.z:.2f}"
                    f" | {self._text('viewer.field.end_z', 'end_z', '终点高程')}={end.z:.2f}"
                    f" | {self._text('viewer.field.length', 'length', '长度')}={length:.2f}"
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

        t = ((px - ax) * segment_dx + (py - ay) * segment_dy) / segment_length_sq
        t = max(0.0, min(1.0, t))
        closest_x = ax + t * segment_dx
        closest_y = ay + t * segment_dy
        return (px - closest_x) ** 2 + (py - closest_y) ** 2

    def _zoom_status(self, factor: float) -> str:
        if factor > 1:
            return self._text("viewer.zoom.in", "Zoomed in", "视图已放大")

        return self._text("viewer.zoom.out", "Zoomed out", "视图已缩小")

    def process_support_commands(self) -> bool:
        """Process queued support commands and report visible state changes."""
        if self.command_queue is None:
            return False

        frame_changed = False

        while True:
            try:
                request = self.command_queue.get_nowait()
            except Empty:
                return frame_changed

            previous_state = replace(self.state)
            previous_viewport = self.viewport
            previous_project_state = self.project_state
            previous_config = self.project_state.config
            was_frame_dirty = self._frame_dirty

            response = self.handle_support_command(request.text)
            request.reply_queue.put(response)
            frame_changed = frame_changed or (
                self.state != previous_state
                or self.viewport != previous_viewport
                or self.project_state is not previous_project_state
                or self.project_state.config != previous_config
                or (self._frame_dirty and not was_frame_dirty)
            )

    def handle_support_command(self, command: str) -> str:
        """Handle one text command from the support panel."""
        stripped_command = command.strip()
        parts = stripped_command.lower().split()

        if not parts:
            return self._text(
                "viewer.command.empty", "ERROR: empty command", "ERROR: 命令不能为空"
            )

        if parts == ["ping"]:
            return "OK: viewer ready"

        if parts == ["mode"]:
            return f"OK: mode={self.state.interaction_mode}"

        if parts in (["viewport"], ["viewport", "summary"]):
            return (
                "OK: "
                f"view={self.viewport.view_width}x{self.viewport.view_height} "
                f"bounds={self.viewport.world_min_x:.9g},"
                f"{self.viewport.world_min_y:.9g},"
                f"{self.viewport.world_max_x:.9g},"
                f"{self.viewport.world_max_y:.9g} "
                f"status={self.state.status_message}"
            )

        if parts == ["mode", "info"]:
            self.state.interaction_mode = "info"
            self.state.status_message = self._text(
                "viewer.mode.info", "Info mode", "要素查询模式"
            )
            return "OK: mode=info"

        if parts == ["mode", "normal"]:
            self.state.interaction_mode = "normal"
            self.state.status_message = self._text(
                "viewer.mode.normal", "Normal mode", "普通浏览模式"
            )
            return "OK: mode=normal"

        if parts == ["selected", "feature"]:
            return f"OK: {self.state.selected_feature}"

        if parts == ["layers", "summary"]:
            return (
                "OK: "
                f"points={'on' if self.state.show_points else 'off'} "
                f"terrain={'on' if self.state.show_terrain else 'off'} "
                f"grid={'on' if self.state.show_grid else 'off'} "
                f"tin={'on' if self.state.show_tin else 'off'} "
                f"contours={'on' if self.state.show_contours else 'off'} "
                f"contour_labels="
                f"{'on' if self.state.show_contour_labels else 'off'} "
                f"contour_source={self.state.contour_source} "
                f"contour_interval={self.state.contour_interval:g} "
                f"terrain_source={self.state.contour_source} "
                f"terrain_opacity={self.state.terrain_opacity:g} "
                f"terrain_palette={self.state.terrain_palette}"
            )

        if parts == ["terrain", "summary"]:
            return (
                "OK: "
                f"source={self.state.contour_source}, "
                f"palette={self.state.terrain_palette}, "
                f"opacity={self.state.terrain_opacity:g}"
            )

        if parts == ["show", "terrain"]:
            self.state.show_terrain = True
            self.state.status_message = self._visibility_status("terrain", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "terrain"]:
            self.state.show_terrain = False
            self.state.status_message = self._visibility_status("terrain", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "terrain"]:
            self.state.show_terrain = not self.state.show_terrain
            self.state.status_message = self._visibility_status(
                "terrain",
                self.state.show_terrain,
            )
            return f"OK: {self.state.status_message}"

        if len(parts) == 3 and parts[:2] == ["terrain", "opacity"]:
            return self._set_terrain_opacity(parts[2])

        if len(parts) == 4 and parts[:3] == ["set", "terrain", "opacity"]:
            return self._set_terrain_opacity(parts[3])

        if len(parts) == 3 and parts[:2] in (
            ["terrain", "palette"],
            ["terrain", "color"],
            ["terrain", "colour"],
        ):
            return self._set_terrain_palette(parts[2])

        if len(parts) == 4 and parts[:3] in (
            ["set", "terrain", "palette"],
            ["set", "terrain", "color"],
            ["set", "terrain", "colour"],
        ):
            return self._set_terrain_palette(parts[3])

        if parts == ["cycle", "terrain", "palette"]:
            return self._cycle_terrain_palette()

        if parts == ["show", "grid"]:
            self.state.show_grid = True
            self.state.status_message = self._visibility_status("grid", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "grid"]:
            self.state.show_grid = False
            self.state.status_message = self._visibility_status("grid", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "grid"]:
            self.state.show_grid = not self.state.show_grid
            self.state.status_message = self._visibility_status(
                "grid",
                self.state.show_grid,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "tin"]:
            self.state.show_tin = True
            self.state.status_message = self._visibility_status("tin", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "tin"]:
            self.state.show_tin = False
            self.state.status_message = self._visibility_status("tin", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "tin"]:
            self.state.show_tin = not self.state.show_tin
            self.state.status_message = self._visibility_status(
                "tin",
                self.state.show_tin,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "points"]:
            self.state.show_points = True
            self.state.status_message = self._visibility_status("points", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "points"]:
            self.state.show_points = False
            self.state.status_message = self._visibility_status("points", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "points"]:
            self.state.show_points = not self.state.show_points
            self.state.status_message = self._visibility_status(
                "points",
                self.state.show_points,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "contours"]:
            self.state.show_contours = True
            self.state.status_message = self._visibility_status("contours", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "contours"]:
            self.state.show_contours = False
            self.state.status_message = self._visibility_status("contours", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "contours"]:
            self.state.show_contours = not self.state.show_contours
            self.state.status_message = self._visibility_status(
                "contours",
                self.state.show_contours,
            )
            return f"OK: {self.state.status_message}"

        if parts == ["show", "contour", "labels"]:
            self.state.show_contour_labels = True
            self.state.status_message = self._visibility_status("contour_labels", True)
            return f"OK: {self.state.status_message}"

        if parts == ["hide", "contour", "labels"]:
            self.state.show_contour_labels = False
            self.state.status_message = self._visibility_status("contour_labels", False)
            return f"OK: {self.state.status_message}"

        if parts == ["toggle", "contour", "labels"]:
            self.state.show_contour_labels = not self.state.show_contour_labels
            self.state.status_message = self._visibility_status(
                "contour_labels",
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
            self.state.status_message = self._text(
                "viewer.viewport.reset", "Viewport reset", "视图已重置"
            )
            return f"OK: {self.state.status_message}"

        if parts == ["summary"]:
            return self.model_summary()

        if len(parts) == 4 and parts[:2] == ["query", "grid"]:
            try:
                row = int(parts[2])
                col = int(parts[3])
            except ValueError:
                return self._text(
                    "viewer.grid.query.integer_error",
                    "ERROR: row and col must be integers",
                    "ERROR: 行号和列号必须是整数",
                )

            try:
                x, y, z = self.project_state.grid.grid_intersection(row, col)
            except ValueError as error:
                return f"ERROR: {error}"

            self.state.status_message = self._text(
                "viewer.grid.query.status",
                "Grid row={row}, col={col}, z={z:.3f}",
                "网格 行={row}，列={col}，高程={z:.3f}",
                row=row,
                col=col,
                z=z,
            )
            return (
                self._text(
                    "viewer.grid.query.result",
                    "OK: grid intersection row={row}, col={col}, ",
                    "OK: 网格交点 行={row}，列={col}，",
                    row=row,
                    col=col,
                )
                + f"x={x:.3f}, y={y:.3f}, z={z:.3f}"
            )

        if parts == ["quit", "viewer"]:
            self.state.running = False
            return self._text(
                "viewer.quitting", "OK: viewer quitting", "OK: 查看器正在退出"
            )

        return self._text(
            "viewer.command.unknown",
            "ERROR: unknown command: {command}",
            "ERROR: 未知命令：{command}",
            command=command,
        )

    def model_summary(self) -> str:
        """Return a short model summary."""
        return self._text(
            "viewer.model.summary",
            "OK: points={points}, grid={grid_x}x{grid_y}, tin_vertices={vertices}, "
            "tin_triangles={triangles}, dataset={dataset}, interpolation={interpolation}",
            "OK: 点数={points}，网格={grid_x}x{grid_y}，TIN 顶点数={vertices}，"
            "TIN 三角形数={triangles}，数据集={dataset}，插值方法={interpolation}",
            points=len(self.project_state.points),
            grid_x=self.project_state.grid.x_divisions,
            grid_y=self.project_state.grid.y_divisions,
            vertices=len(self.project_state.tin.vertices),
            triangles=len(self.project_state.tin.triangles),
            dataset=self.project_state.config.dataset_path,
            interpolation=self.project_state.config.interpolation_method,
        )

    def contour_summary(self) -> str:
        """Return a short contour summary for the current contour settings."""
        polylines = self.contour_polylines()
        open_count = sum(1 for polyline in polylines if not polyline.closed)
        closed_count = sum(1 for polyline in polylines if polyline.closed)

        if self.state.contour_source == "tin":
            value_min, value_max = tin_value_range(self.project_state.tin)
        else:
            value_min, value_max = grid_value_range(self.project_state.grid)

        levels = generate_contour_levels(
            value_min,
            value_max,
            self.state.contour_interval,
        )
        return self._text(
            "viewer.contour.summary",
            "OK: source={source}, interval={interval:g}, levels={levels}, "
            "polylines={polylines}, open={open_count}, closed={closed_count}",
            "OK: 数据源={source}，等高距={interval:g}，高程级别数={levels}，"
            "等高线数={polylines}，开放线={open_count}，闭合线={closed_count}",
            source=self._source_label(self.state.contour_source),
            interval=self.state.contour_interval,
            levels=len(levels),
            polylines=len(polylines),
            open_count=open_count,
            closed_count=closed_count,
        )

    def _set_contour_source(self, source: str) -> str:
        """Set contour generation source from a support command."""
        if source not in ("grid", "tin"):
            return self._text(
                "viewer.contour.source_error",
                "ERROR: contour source must be grid or tin",
                "ERROR: 等高线数据源必须为 grid 或 tin",
            )

        self.state.contour_source = source
        self._update_project_config(contour_source=source)
        self.state.status_message = self._text(
            "viewer.contour.source",
            "Contour source: {source}",
            "等高线数据源：{source}",
            source=self._source_label(source),
        )
        return f"OK: {self.state.status_message}"

    def _set_contour_interval(self, value_text: str) -> str:
        """Set contour interval from a support command."""
        try:
            interval = float(value_text)
        except ValueError:
            return self._text(
                "viewer.contour.interval_number_error",
                "ERROR: contour interval must be a number",
                "ERROR: 等高距必须是数字",
            )

        if interval <= 0:
            return self._text(
                "viewer.contour.interval_positive_error",
                "ERROR: contour interval must be positive",
                "ERROR: 等高距必须为正数",
            )

        self.state.contour_interval = interval
        self._update_project_config(contour_interval=interval)
        self.state.status_message = self._text(
            "viewer.contour.interval",
            "Contour interval: {interval:g}",
            "等高距：{interval:g}",
            interval=interval,
        )
        return f"OK: {self.state.status_message}"

    def _set_terrain_opacity(self, value_text: str) -> str:
        """Set simulated terrain opacity from a support command."""
        try:
            opacity = float(value_text)
        except ValueError:
            return self._text(
                "viewer.terrain.opacity_number_error",
                "ERROR: terrain opacity must be a number",
                "ERROR: 地形不透明度必须是数字",
            )

        if 1.0 < opacity <= 100.0:
            opacity = opacity / 100.0

        if opacity < 0.0 or opacity > 1.0:
            return self._text(
                "viewer.terrain.opacity_range_error",
                "ERROR: terrain opacity must be between 0 and 1",
                "ERROR: 地形不透明度必须介于 0 和 1 之间",
            )

        self.state.terrain_opacity = opacity
        self._clear_model_caches()
        self.state.status_message = self._text(
            "viewer.terrain.opacity",
            "Terrain opacity: {opacity:.0%}",
            "地形不透明度：{opacity:.0%}",
            opacity=opacity,
        )
        return f"OK: {self.state.status_message}"

    def _set_terrain_palette(self, palette: str) -> str:
        """Set the terrain colour palette from a support command."""
        palette_name = TERRAIN_PALETTE_ALIASES.get(palette, palette)
        if palette_name not in TERRAIN_PALETTES:
            return self._text(
                "viewer.terrain.palette_error",
                "ERROR: terrain palette must be one of {palettes}",
                "ERROR: 地形色带必须是以下之一：{palettes}",
                palettes=", ".join(TERRAIN_PALETTE_NAMES),
            )

        self.state.terrain_palette = palette_name
        self._clear_model_caches()
        self.state.status_message = self._text(
            "viewer.terrain.palette",
            "Terrain palette: {palette}",
            "地形色带：{palette}",
            palette=self._palette_label(palette_name),
        )
        return f"OK: {self.state.status_message}"

    def _cycle_terrain_palette(self) -> str:
        """Cycle to the next terrain colour palette."""
        current_index = TERRAIN_PALETTE_NAMES.index(self.state.terrain_palette)
        next_index = (current_index + 1) % len(TERRAIN_PALETTE_NAMES)
        return self._set_terrain_palette(TERRAIN_PALETTE_NAMES[next_index])

    def _set_grid_divisions(self, x_text: str, y_text: str) -> str:
        """Set grid divisions and rebuild the project safely."""
        try:
            x_divisions = int(x_text)
            y_divisions = int(y_text)
        except ValueError:
            return self._text(
                "viewer.grid.integer_error",
                "ERROR: grid divisions must be integers",
                "ERROR: 网格划分数必须是整数",
            )

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

        self.state.status_message = self._text(
            "viewer.grid.rebuilding",
            "Rebuilding grid {x}x{y}...",
            "正在重建 {x}x{y} 网格……",
            x=x_divisions,
            y=y_divisions,
        )
        return self._rebuild_project(
            config,
            reset_viewport=False,
            success_message=self._text(
                "viewer.grid.updated",
                "Grid divisions set to {x}x{y}",
                "网格划分数已设为 {x}x{y}",
                x=x_divisions,
                y=y_divisions,
            ),
            failure_prefix=self._text(
                "viewer.grid.rebuild_failed",
                "grid rebuild failed",
                "网格重建失败",
            ),
        )

    def _load_dataset(self, path_text: str) -> str:
        """Load a new dataset without discarding the current project on error."""
        path_text = path_text.strip()
        if not path_text:
            return self._text(
                "viewer.dataset.path_required",
                "ERROR: dataset path is required",
                "ERROR: 必须提供数据集路径",
            )

        try:
            config = replace(
                self.project_state.config,
                dataset_path=Path(path_text),
                contour_source=self.state.contour_source,
                contour_interval=self.state.contour_interval,
            )
        except ValueError as error:
            return f"ERROR: {error}"

        self.state.status_message = self._text(
            "viewer.dataset.loading",
            "Loading dataset {path}...",
            "正在加载数据集 {path}……",
            path=config.dataset_path,
        )
        return self._rebuild_project(
            config,
            reset_viewport=True,
            success_message=self._text(
                "viewer.dataset.loaded",
                "Dataset loaded: {path}",
                "数据集已加载：{path}",
                path=config.dataset_path,
            ),
            failure_prefix=self._text(
                "viewer.dataset.load_failed",
                "dataset load failed",
                "数据集加载失败",
            ),
        )

    def _reload_dataset(self) -> str:
        """Reload the current dataset through the normal project build path."""
        config = replace(
            self.project_state.config,
            contour_source=self.state.contour_source,
            contour_interval=self.state.contour_interval,
        )
        self.state.status_message = self._text(
            "viewer.dataset.reloading",
            "Reloading dataset {path}...",
            "正在重新加载数据集 {path}……",
            path=config.dataset_path,
        )
        return self._rebuild_project(
            config,
            reset_viewport=False,
            success_message=self._text(
                "viewer.dataset.reloaded",
                "Dataset reloaded: {path}",
                "数据集已重新加载：{path}",
                path=config.dataset_path,
            ),
            failure_prefix=self._text(
                "viewer.dataset.reload_failed",
                "dataset reload failed",
                "数据集重新加载失败",
            ),
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
