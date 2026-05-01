import pytest

from primelock_gis.core.algorithms.interpolation import idw_value
from primelock_gis.core.models.vector import SpecialPoint


def test_idw_value_midpoint_between_equal_distance_points():
    points = [
        SpecialPoint(id=1, name="A", x=0.0, y=0.0, z=10.0),
        SpecialPoint(id=2, name="B", x=10.0, y=0.0, z=20.0),
    ]

    assert idw_value(points, 5.0, 0.0) == pytest.approx(15.0)


def test_idw_value_returns_exact_point_value():
    points = [
        SpecialPoint(id=1, name="A", x=0.0, y=0.0, z=10.0),
        SpecialPoint(id=2, name="B", x=10.0, y=0.0, z=20.0),
    ]

    assert idw_value(points, 0.0, 0.0) == 10.0