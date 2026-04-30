from pathlib import Path
from primelock_gis.core.load_data import (
    load_sample_points,
    load_normalised_sample_points,
    normalise_sample_points,
)
from primelock_gis.core.models.vector import SpecialPoint


def test_load_sample_points():
    test_csv_path = Path("data/initial_coords.csv")
    points = load_sample_points(test_csv_path)

    assert len(points) > 0
    assert isinstance(points[0], SpecialPoint)

    # load_sample_points() should keep original coordinates
    assert points[0].x != 0
    assert points[0].y != 0


def test_load_normalised_sample_points():
    test_csv_path = Path("data/initial_coords.csv")
    points = load_normalised_sample_points(test_csv_path)

    assert len(points) > 0
    assert isinstance(points[0], SpecialPoint)

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)

    assert min_x == 0
    assert min_y == 0


def test_normalise_sample_points():
    points = [
        SpecialPoint(id=1, name="A", x=100.0, y=200.0, z=10.0),
        SpecialPoint(id=2, name="B", x=150.0, y=250.0, z=20.0),
    ]
    normalised = normalise_sample_points(points)

    assert normalised[0].x == 0
    assert normalised[0].y == 0
    assert normalised[1].x == 50
    assert normalised[1].y == 50
    assert normalised[0].z == 10.0
    assert normalised[1].z == 20.0