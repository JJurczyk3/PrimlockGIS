""" Terminal application loop """
import shutil
from .canvas import TerminalCanvas
from .capabilities import TerminalCapabilities
from .renderer2d import TerminalRenderer2D
from primelock_gis.core.rendering.scene import Scene
from primelock_gis.core.rendering.viewport import Viewport


class TerminalApp:
    def __init__(self, scene, viewport, capabilities):
        self.scene = scene
        self.viewport = viewport
        self.capabilities = capabilities

        self.canvas = None
        self.renderer = None
        self.last_width = 0
        self.last_height = 0

        self.build_renderer()

    def build_renderer(self) -> None:
        """Rebuild the renderer with the current viewport size."""
        height = self.viewport.view_height
        width = self.viewport.view_width
        self.canvas = TerminalCanvas(width, height)
        self.renderer = TerminalRenderer2D(self.canvas, self.viewport, self.capabilities)
        self.last_height = height
        self.last_width = width

    def redraw(self) -> str:
        """Clear the canvas, render the scene, and return the rendered text."""
        self.renderer.render_scene(self.scene)
        return self.renderer.to_string()

    def resize_if_needed(self) -> None:
        """Check if the terminal size has changed and rebuild the renderer if so."""
        size = shutil.get_terminal_size()
        width = size.columns
        height = size.lines
        if width != self.last_width or height != self.last_height:
            self.viewport = self.viewport.resize_viewport(width, height)
            self.build_renderer()
        