"""Datastructures for TIN generation."""

from dataclasses import dataclass


@dataclass
class TinVertex:
    id: int
    x: float
    y: float
    z: float = 0.0
    source_point_id: int | None = None


@dataclass
class TinTriangle:
    id: int
    vertex_ids: tuple[int, int, int]


@dataclass
class TinModel:
    vertices: list[TinVertex]
    triangles: list[TinTriangle]
