"""Interactive terminal app set-up."""

from dataclasses import dataclass
import shutil

from primelock_gis.app.project_state import ProjectState
from primelock_gis.core.rendering.scene import Scene
from primelock_gis.core.rendering.scene_builder import (
    grid_to_scene,
    points_to_scene,
    tin_to_scene,
)
from primelock_gis.core.rendering.symbology import PointStyle, PolylineStyle
from primelock_gis.core.rendering.viewport import Viewport
from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
from primelock_gis.ui.terminal.input import read_key_event
from primelock_gis.ui.terminal.render_app import TerminalRenderApp
from primelock_gis.ui.terminal.screen import clear_screen, draw_frame, draw_status_bar
from primelock_gis.ui.terminal.session import TerminalSession


@dataclass
class InteractiveState:
    running: bool = True
    show_points: bool = True
    show_grid: bool = False
    show_tin: bool = True
    status_message: str = "Ready"


class InteractiveTerminalApp:
    """Run the interactive terminal GIS application."""

    def __init__(
        self,
        project_state: ProjectState,
        viewport: Viewport,
        capabilities: TerminalCapabilities,
    ) -> None:
        self.project_state = project_state
        self.viewport = viewport
        self.initial_viewport = viewport
        self.capabilities = capabilities
        self.state = InteractiveState()

    def build_scene(self) -> Scene:
        """Build the currently visible scene from enabled layers."""
        scene = Scene()

        if self.state.show_grid:
            grid_scene = grid_to_scene(
                self.project_state.idw_grid,
                style=PolylineStyle(char="."),
            )
            self._merge_scene(scene, grid_scene)

        if self.state.show_tin:
            tin_scene = tin_to_scene(
                self.project_state.tin,
                style=PolylineStyle(char="*"),
            )
            self._merge_scene(scene, tin_scene)

        if self.state.show_points:
            point_scene = points_to_scene(
                self.project_state.points,
                style=PointStyle(char="●"),
            )
            self._merge_scene(scene, point_scene)

        return scene

    def render_frame(self) -> str:
        """Render the current visible scene to terminal text."""
        scene = self.build_scene()

        render_app = TerminalRenderApp(
            scene=scene,
            viewport=self.viewport,
            capabilities=self.capabilities,
        )

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

        if key == "r":
            self.viewport = self.initial_viewport
            self.state.status_message = "Viewport reset"
            return

        self.state.status_message = f"Unknown key: {repr(key)}"

    def resize_if_needed(self) -> int:
        """Resize viewport to match the terminal and return the status-row number."""
        terminal_size = shutil.get_terminal_size()
        width = terminal_size.columns
        height = max(1, terminal_size.lines - 1)

        if width != self.viewport.view_width or height != self.viewport.view_height:
            self.viewport = self.viewport.resize_viewport(width, height)
            self.initial_viewport = self.initial_viewport.resize_viewport(width, height)
            self.state.status_message = f"Resized to {width}x{height}"

        return terminal_size.lines

    def run(self) -> None:
        """Run the interactive terminal application loop."""
        with TerminalSession():
            clear_screen()

            while self.state.running:
                status_row = self.resize_if_needed()

                frame = self.render_frame()

                clear_screen()
                draw_frame(frame)
                draw_status_bar(self.status_text(), row=status_row)

                event = read_key_event(timeout=0.05)

                if event is not None:
                    self.handle_key(event.key)

    def status_text(self) -> str:
        """Return the status bar text."""
        return (
            "q quit | g grid | t TIN | p points | r reset "
            f"| grid={self.state.show_grid} "
            f"| tin={self.state.show_tin} "
            f"| points={self.state.show_points} "
            f"| {self.state.status_message}"
        )

    def _merge_scene(self, target: Scene, source: Scene) -> None:
        """Merge one scene into another scene."""
        target.polygons.extend(source.polygons)
        target.polylines.extend(source.polylines)
        target.points.extend(source.points)
        target.texts.extend(source.texts)

    def _visibility_status(self, layer_name: str, visible: bool) -> str:
        """Return a short visibility status message."""
        if visible:
            return f"{layer_name} visible"

        return f"{layer_name} hidden"