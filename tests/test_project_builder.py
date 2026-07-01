from pathlib import Path

from primelock_gis.app.project_builder import (
    build_project_state,
    try_rebuild_project_state,
)
from primelock_gis.app.project_state import ProjectConfig


def write_points_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "No.,Data point name,x_coord,y_coord,z_coord",
                "1,A,0,0,10",
                "2,B,10,0,20",
                "3,C,0,10,30",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_project_state_uses_project_config(tmp_path):
    csv_path = tmp_path / "points.csv"
    write_points_csv(csv_path)

    state = build_project_state(
        ProjectConfig(
            dataset_path=csv_path,
            grid_x_divisions=3,
            grid_y_divisions=4,
        )
    )

    assert state.config.dataset_path == csv_path
    assert state.idw_grid.x_divisions == 3
    assert state.idw_grid.y_divisions == 4
    assert len(state.points) == 3


def test_try_rebuild_project_state_keeps_current_project_on_load_failure(tmp_path):
    csv_path = tmp_path / "points.csv"
    write_points_csv(csv_path)
    current = build_project_state(ProjectConfig(dataset_path=csv_path))

    result = try_rebuild_project_state(
        current,
        ProjectConfig(dataset_path=tmp_path / "missing.csv"),
    )

    assert result.success is False
    assert result.project_state is current
    assert current.config.dataset_path == csv_path
