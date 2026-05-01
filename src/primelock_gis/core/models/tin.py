"""TIN data models for Primelock GIS."""

from dataclasses import dataclass


@dataclass
class TinVertex:
    """A vertex used by future TIN workflows."""

    id: int
    x: float
    y: float
    z: float = 0.0
    source_point_id: int | None = None
