"""Data structures for TIN generation and topology."""

from dataclasses import dataclass

TinEdgeKey = tuple[int, int]


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
    # Neighbor across each implied edge:
    neighbor_triangle_ids: tuple[int | None, int | None, int | None] = (
        None,
        None,
        None,
    )
    # GIS arc or boundary represented by each triangle edge. None means this
    # is an ordinary internal triangulation edge for now.
    edge_arc_ids: tuple[int | None, int | None, int | None] = (
        None,
        None,
        None,
    )
    containing_polygon_id: int | None = None

    def edge_vertex_ids(self, edge_index: int) -> tuple[int, int]:
        """Return the ordered vertex ids for one implied triangle edge."""
        if edge_index == 0:
            return self.vertex_ids[0], self.vertex_ids[1]
        if edge_index == 1:
            return self.vertex_ids[1], self.vertex_ids[2]
        if edge_index == 2:
            return self.vertex_ids[2], self.vertex_ids[0]

        raise ValueError("TIN triangle edge index must be 0, 1, or 2")

    def edge_key(self, edge_index: int) -> TinEdgeKey:
        """Return an undirected stable key for one implied triangle edge."""
        return tuple(sorted(self.edge_vertex_ids(edge_index)))


@dataclass
class TinModel:
    vertices: list[TinVertex]
    triangles: list[TinTriangle]

    def vertex_by_id(self) -> dict[int, TinVertex]:
        """Return vertices indexed by TIN vertex id."""
        return {vertex.id: vertex for vertex in self.vertices}

    def triangle_by_id(self) -> dict[int, TinTriangle]:
        """Return triangles indexed by TIN triangle id."""
        return {triangle.id: triangle for triangle in self.triangles}

    def unique_edge_keys(self) -> set[TinEdgeKey]:
        """Return all unique undirected triangle edges in the model."""
        edges = set()

        for triangle in self.triangles:
            for edge_index in range(3):
                edges.add(triangle.edge_key(edge_index))

        return edges
