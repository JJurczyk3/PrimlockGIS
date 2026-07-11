"""Build and rebuild project state from project configuration."""

from dataclasses import dataclass

from primelock_gis.app.project_state import ProjectConfig, ProjectState
from primelock_gis.core.algorithms.grid import (
    create_grid_model_directional,
    create_grid_model_idw,
)
from primelock_gis.core.algorithms.tin import build_tin_from_points
from primelock_gis.core.load_data import load_normalised_sample_points


@dataclass
class ProjectRebuildResult:
    """Result of a safe project rebuild attempt."""

    project_state: ProjectState
    success: bool
    message: str


def build_project_state(config: ProjectConfig) -> ProjectState:
    """Build all computed project models from configuration."""
    points = load_normalised_sample_points(config.dataset_path)

    # Startup, dataset reloads, and grid setting changes all pass through this
    # function so every computed model stays tied to the same ProjectConfig.
    if config.interpolation_method == "directional":
        idw_grid = create_grid_model_directional(
            points,
            x_divisions=config.grid_x_divisions,
            y_divisions=config.grid_y_divisions,
        )
    else:
        idw_grid = create_grid_model_idw(
            points,
            x_divisions=config.grid_x_divisions,
            y_divisions=config.grid_y_divisions,
        )

    tin = build_tin_from_points(points)
    return ProjectState(
        points=points,
        idw_grid=idw_grid,
        tin=tin,
        config=config,
    )


def try_rebuild_project_state(
    current_state: ProjectState,
    config: ProjectConfig,
) -> ProjectRebuildResult:
    """Build a replacement project without discarding the current one on error."""
    try:
        next_state = build_project_state(config)
    except Exception as error:
        return ProjectRebuildResult(
            project_state=current_state,
            success=False,
            message=str(error),
        )

    return ProjectRebuildResult(
        project_state=next_state,
        success=True,
        message="project rebuilt",
    )
