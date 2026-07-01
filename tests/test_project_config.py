from pathlib import Path

import pytest

from primelock_gis.app.project_state import ProjectConfig


def test_project_config_accepts_valid_settings():
    config = ProjectConfig(
        dataset_path="data/initial_coords.csv",
        grid_x_divisions=30,
        grid_y_divisions=40,
        interpolation_method="IDW",
        contour_interval=25.0,
        contour_source="TIN",
    )

    assert config.dataset_path == Path("data/initial_coords.csv")
    assert config.grid_x_divisions == 30
    assert config.grid_y_divisions == 40
    assert config.interpolation_method == "idw"
    assert config.contour_source == "tin"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"grid_x_divisions": 0}, "grid_x_divisions must be positive"),
        ({"grid_y_divisions": "20"}, "grid_y_divisions must be an integer"),
        ({"interpolation_method": "kriging"}, "interpolation_method"),
        ({"contour_interval": 0}, "contour_interval must be positive"),
        ({"contour_source": "terrain"}, "contour_source must be grid or tin"),
    ],
)
def test_project_config_rejects_invalid_settings(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ProjectConfig(**kwargs)
