"""Load and normalise GIS data from files."""

from pathlib import Path
import polars as pl
from primelock_gis.core.models.vector import SpecialPoint


def load_sample_points(file_path: Path) -> list[SpecialPoint]:
    """Load coordinate points from a CSV file."""
    df = pl.read_csv(file_path)
    df = clean_dataframe_column_names(df)
    points = []

    for row in df.iter_rows(named=True):
        point = SpecialPoint(
            id=int(row["No."]),
            name=row["Data point name"],
            x=float(row["x_coord"]),
            y=float(row["y_coord"]),
            z=float(row["z_coord"]),
        )
        points.append(point)
    return points


def load_normalised_sample_points(file_path: Path) -> list[SpecialPoint]:
    """Load sample points and normalise their x/y coordinates."""
    points = load_sample_points(file_path)
    return normalise_sample_points(points)


def normalise_sample_points(points: list[SpecialPoint]) -> list[SpecialPoint]:
    """Shift x and y coordinates so the minimum x and y become zero."""
    if not points:
        return []

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    normalised_points = []

    for point in points:
        normalised_point = SpecialPoint(
            id=point.id,
            name=point.name,
            x=point.x - min_x,
            y=point.y - min_y,
            z=point.z,
            outer_polygon=point.outer_polygon,
        )
        normalised_points.append(normalised_point)
    return normalised_points


def clean_dataframe_column_names(df: pl.DataFrame) -> pl.DataFrame:
    """Remove extra spaces from CSV column names."""
    clean_names = {}

    for column in df.columns:
        clean_names[column] = column.strip()

    return df.rename(clean_names)
