"""Application startup workflow."""

from pathlib import Path
import shutil

from primelock_gis.app.project_state import ProjectState
from primelock_gis.core.algorithms.grid import create_grid_model_idw
from primelock_gis.core.algorithms.tin import build_tin_from_points
from primelock_gis.core.load_data import load_normalised_sample_points
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.ui.terminal.capabilities import detect_terminal_capabilities
from primelock_gis.ui.terminal.interactive_app import InteractiveTerminalApp


def run_terminal_beta(
        csv_path: Path | None = None,
        grid_x_division: int = 8,
        grid_y_division: int = 8,
) -> None:
    """Start the interactive terminal beta application."""
    if csv_path is None:
        csv_path = Path("data/initial_coords.csv")

    points = load_normalised_sample_points(csv_path)

    idw_grid = create_grid_model_idw(
        points,
        x_divisions=grid_x_division,
        y_divisions=grid_x_division,
    )

    tin = build_tin_from_points(points)

    project_state = ProjectState(
        points=points,
        idw_grid=idw_grid,
        tin=tin,
    )

    terminal_size = shutil.get_terminal_size()
    view_width = terminal_size.columns
    view_height = max(1, terminal_size.lines - 1)

    viewport = initial_viewport_from_points(
        points,
        view_width=view_width,
        view_height=view_height,
        padding=0.05,
    )

    capabilities = detect_terminal_capabilities()

    app = InteractiveTerminalApp(
        project_state=project_state,
        viewport=viewport,
        capabilities=capabilities,
    )

    app.run()