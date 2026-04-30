@dataclass
class TinVertex:
    id: int
    x: float
    y: float
    z: float = 0.0
    source_point_id: int | None = None