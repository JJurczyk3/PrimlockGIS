"""Data structures for TIN generation and topology."""

from dataclasses import dataclass, field
import math

TinEdgeKey = tuple[int, int]
TIN_CONTAINMENT_TOLERANCE = 1e-9


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


@dataclass(frozen=True)
class _TinSurfaceTriangle:
    a: TinVertex
    b: TinVertex
    c: TinVertex
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    denominator: float

    @classmethod
    def from_vertices(
        cls,
        a: TinVertex,
        b: TinVertex,
        c: TinVertex,
    ) -> "_TinSurfaceTriangle | None":
        denominator = (
            (b.y - c.y) * (a.x - c.x)
            + (c.x - b.x) * (a.y - c.y)
        )

        if abs(denominator) <= TIN_CONTAINMENT_TOLERANCE:
            return None

        return cls(
            a=a,
            b=b,
            c=c,
            min_x=min(a.x, b.x, c.x),
            min_y=min(a.y, b.y, c.y),
            max_x=max(a.x, b.x, c.x),
            max_y=max(a.y, b.y, c.y),
            denominator=denominator,
        )

    def sample_at(self, x: float, y: float) -> float | None:
        if (
            x < self.min_x - TIN_CONTAINMENT_TOLERANCE
            or x > self.max_x + TIN_CONTAINMENT_TOLERANCE
            or y < self.min_y - TIN_CONTAINMENT_TOLERANCE
            or y > self.max_y + TIN_CONTAINMENT_TOLERANCE
        ):
            return None

        wa = (
            (self.b.y - self.c.y) * (x - self.c.x)
            + (self.c.x - self.b.x) * (y - self.c.y)
        ) / self.denominator
        wb = (
            (self.c.y - self.a.y) * (x - self.c.x)
            + (self.a.x - self.c.x) * (y - self.c.y)
        ) / self.denominator
        wc = 1.0 - wa - wb

        if (
            wa < -TIN_CONTAINMENT_TOLERANCE
            or wb < -TIN_CONTAINMENT_TOLERANCE
            or wc < -TIN_CONTAINMENT_TOLERANCE
        ):
            return None

        return wa * self.a.z + wb * self.b.z + wc * self.c.z


@dataclass
class _TinSurfaceIndex:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    x_bins: int
    y_bins: int
    cells: list[list[_TinSurfaceTriangle]]

    @classmethod
    def build(
        cls,
        triangles: list[_TinSurfaceTriangle],
        bounds: tuple[float, float, float, float],
    ) -> "_TinSurfaceIndex":
        min_x, min_y, max_x, max_y = bounds
        side = max(1, min(64, round(math.sqrt(max(1, len(triangles))))))
        cells: list[list[_TinSurfaceTriangle]] = [[] for _ in range(side * side)]
        index = cls(
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
            x_bins=side,
            y_bins=side,
            cells=cells,
        )

        for triangle in triangles:
            min_col, min_row = index._cell_for_point(triangle.min_x, triangle.min_y)
            max_col, max_row = index._cell_for_point(triangle.max_x, triangle.max_y)

            for row in range(min_row, max_row + 1):
                for col in range(min_col, max_col + 1):
                    cells[index._cell_index(col, row)].append(triangle)

        return index

    def candidates_at(self, x: float, y: float) -> list[_TinSurfaceTriangle]:
        if (
            x < self.min_x
            or x > self.max_x
            or y < self.min_y
            or y > self.max_y
        ):
            return []

        col, row = self._cell_for_point(x, y)
        return self.cells[self._cell_index(col, row)]

    def _cell_for_point(self, x: float, y: float) -> tuple[int, int]:
        col = self._axis_cell(x, self.min_x, self.max_x, self.x_bins)
        row = self._axis_cell(y, self.min_y, self.max_y, self.y_bins)
        return col, row

    def _axis_cell(
        self,
        value: float,
        axis_min: float,
        axis_max: float,
        bins: int,
    ) -> int:
        if axis_max == axis_min:
            return 0

        scaled = (value - axis_min) / (axis_max - axis_min) * bins
        return max(0, min(bins - 1, int(scaled)))

    def _cell_index(self, col: int, row: int) -> int:
        return row * self.x_bins + col


@dataclass
class TinModel:
    vertices: list[TinVertex]
    triangles: list[TinTriangle]
    _vertex_by_id_cache: dict[int, TinVertex] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _bounds_cache: tuple[float, float, float, float] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _value_range_cache: tuple[float, float] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _surface_triangles_cache: list[_TinSurfaceTriangle] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _surface_index_cache: _TinSurfaceIndex | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def vertex_by_id(self) -> dict[int, TinVertex]:
        """Return vertices indexed by TIN vertex id."""
        return dict(self._cached_vertex_by_id())

    def _cached_vertex_by_id(self) -> dict[int, TinVertex]:
        """Return the cached vertex lookup used by repeated surface sampling."""
        if self._vertex_by_id_cache is None:
            self._vertex_by_id_cache = {
                vertex.id: vertex for vertex in self.vertices
            }

        return self._vertex_by_id_cache

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

    def bounds(self) -> tuple[float, float, float, float]:
        """Return x/y bounds as x_min, y_min, x_max, y_max."""
        if self._bounds_cache is not None:
            return self._bounds_cache

        if not self.vertices:
            raise ValueError("TIN has no vertices")

        self._bounds_cache = (
            min(vertex.x for vertex in self.vertices),
            min(vertex.y for vertex in self.vertices),
            max(vertex.x for vertex in self.vertices),
            max(vertex.y for vertex in self.vertices),
        )
        return self._bounds_cache

    def value_range(self) -> tuple[float, float]:
        """Return the minimum and maximum vertex z values."""
        if self._value_range_cache is not None:
            return self._value_range_cache

        if not self.vertices:
            raise ValueError("TIN has no vertices")

        values = [vertex.z for vertex in self.vertices]
        self._value_range_cache = min(values), max(values)
        return self._value_range_cache

    def contains_xy(self, x: float, y: float) -> bool:
        """Return True if a world coordinate lies inside any TIN triangle."""
        return self.sample_at(x, y) is not None

    def sample_at(self, x: float, y: float) -> float | None:
        """Return the interpolated TIN value or None outside the TIN hull."""
        for triangle in self._surface_index().candidates_at(x, y):
            value = triangle.sample_at(x, y)
            if value is not None:
                return value

        return None

    def value_at(self, x: float, y: float) -> float:
        """Return the linearly interpolated TIN value at a world coordinate."""
        value = self.sample_at(x, y)
        if value is None:
            raise ValueError("Point is outside TIN bounds")

        return value

    def _surface_triangles(self) -> list[_TinSurfaceTriangle]:
        if self._surface_triangles_cache is not None:
            return self._surface_triangles_cache

        vertices_by_id = self._cached_vertex_by_id()
        surface_triangles = []

        for triangle in self.triangles:
            a = vertices_by_id[triangle.vertex_ids[0]]
            b = vertices_by_id[triangle.vertex_ids[1]]
            c = vertices_by_id[triangle.vertex_ids[2]]
            surface_triangle = _TinSurfaceTriangle.from_vertices(a, b, c)
            if surface_triangle is not None:
                surface_triangles.append(surface_triangle)

        self._surface_triangles_cache = surface_triangles
        return self._surface_triangles_cache

    def _surface_index(self) -> _TinSurfaceIndex:
        if self._surface_index_cache is None:
            self._surface_index_cache = _TinSurfaceIndex.build(
                self._surface_triangles(),
                self.bounds(),
            )

        return self._surface_index_cache
