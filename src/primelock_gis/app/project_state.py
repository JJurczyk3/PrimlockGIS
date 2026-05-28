"""Application project state."""

from dataclasses import dataclass

from primelock_gis.core.models.grid import GridModel
from primelock_gis.core.models.tin import TinModel
from primelock_gis.core.models.vector import SpecialPoint


@dataclass
class ProjectState:
    points: list[SpecialPoint]
    idw_grid: GridModel
    tin: TinModel