"""Application startup workflow."""

from pathlib import Path
import shutil
from queue import Queue

from primelock_gis.app.project_builder import build_project_state
from primelock_gis.app.project_state import ProjectConfig
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.ui.terminal.capabilities import detect_terminal_capabilities
from primelock_gis.ui.terminal.interactive_app import InteractiveTerminalApp
from primelock_gis.ui.terminal.support_panel import CommandRequest, start_command_server


def run_terminal_beta(
        csv_path: Path | None = None,
        grid_x_division: int = 8,
        grid_y_division: int = 8,
) -> None:
    """Start the interactive terminal beta application."""
    if csv_path is None:
        csv_path = Path("data/initial_coords.csv")

    project_state = build_project_state(
        ProjectConfig(
            dataset_path=csv_path,
            grid_x_divisions=grid_x_division,
            grid_y_divisions=grid_y_division,
        )
    )

    terminal_size = shutil.get_terminal_size()
    view_width = terminal_size.columns
    view_height = max(1, terminal_size.lines - 1)

    viewport = initial_viewport_from_points(
        project_state.points,
        view_width=view_width,
        view_height=view_height,
        padding=0.05,
    )

    capabilities = detect_terminal_capabilities()

    command_queue: Queue[CommandRequest] = Queue()
    server = start_command_server(command_queue)

    app = InteractiveTerminalApp(
        project_state=project_state,
        viewport=viewport,
        capabilities=capabilities,
        command_queue=command_queue,
    )

    try:
        app.run()
    finally:
        server.shutdown()
        server.server_close()
