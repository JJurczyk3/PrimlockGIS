"""Application project configuration and computed state."""

from dataclasses import dataclass
from pathlib import Path

from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel
from primelock_gis.core.models.vector import SpecialPoint


@dataclass
class ProjectConfig:
    """Settings used to build the current project models."""

    dataset_path: Path = Path("data/initial_coords.csv")
    grid_x_divisions: int = 20
    grid_y_divisions: int = 20
    interpolation_method: str = "idw"
    contour_interval: float = 50.0
    contour_source: str = "grid"

    def __post_init__(self) -> None:
        self.dataset_path = Path(self.dataset_path)
        if not isinstance(self.interpolation_method, str):
            raise ValueError("interpolation_method must be idw or directional")
        if not isinstance(self.contour_source, str):
            raise ValueError("contour_source must be grid or tin")

        self.interpolation_method = self.interpolation_method.lower()
        self.contour_source = self.contour_source.lower()

        if not isinstance(self.grid_x_divisions, int):
            raise ValueError("grid_x_divisions must be an integer")
        if not isinstance(self.grid_y_divisions, int):
            raise ValueError("grid_y_divisions must be an integer")
        if self.grid_x_divisions < 1:
            raise ValueError("grid_x_divisions must be positive")
        if self.grid_y_divisions < 1:
            raise ValueError("grid_y_divisions must be positive")

        if self.interpolation_method not in ("idw", "directional"):
            raise ValueError("interpolation_method must be idw or directional")

        if not isinstance(self.contour_interval, int | float):
            raise ValueError("contour_interval must be a number")
        if self.contour_interval <= 0:
            raise ValueError("contour_interval must be positive")
        if self.contour_source not in ("grid", "tin"):
            raise ValueError("contour_source must be grid or tin")

    def summary(self) -> str:
        """Return a compact text summary suitable for support-panel commands."""
        return (
            f"dataset={self.dataset_path} "
            f"grid={self.grid_x_divisions}x{self.grid_y_divisions} "
            f"interpolation={self.interpolation_method} "
            f"contour_source={self.contour_source} "
            f"contour_interval={self.contour_interval:g}"
        )


@dataclass
class ProjectState:
    points: list[SpecialPoint]
    idw_grid: GridModel
    tin: TinModel
    config: ProjectConfig | None = None

    def __post_init__(self) -> None:
        if self.config is not None:
            return

        self.config = ProjectConfig(
            grid_x_divisions=self.idw_grid.x_divisions,
            grid_y_divisions=self.idw_grid.y_divisions,
        )
