"""Sample point loading/render preparation."""

from pathlib import Path

from primelock_gis.core.load_data import load_normalised_sample_points
from primelock_gis.core.rendering.scene_builder import points_to_scene
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.ui.terminal.capabilities import detect_terminal_capabilities
from primelock_gis.ui.terminal.app import TerminalApp


def render_sample_points_from_csv(
    csv_path: Path,
    view_width: int,
    view_height: int,
) -> str:
    points = load_normalised_sample_points(csv_path)
    scene = points_to_scene(points)
    viewport = initial_viewport_from_points(points, view_width, view_height)
    capabilities = detect_terminal_capabilities()
    app = TerminalApp(scene, viewport, capabilities)
    return app.redraw()