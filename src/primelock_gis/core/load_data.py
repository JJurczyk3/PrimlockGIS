"""Load and normalise GIS data from files."""

from math import isfinite
from pathlib import Path

import polars as pl

from primelock_gis.core.models.vector import SpecialPoint

REQUIRED_POINT_COLUMNS = (
    "No.",
    "Data point name",
    "x_coord",
    "y_coord",
    "z_coord",
)


def load_sample_points(file_path: Path) -> list[SpecialPoint]:
    """Load coordinate points from a CSV file."""
    dataframe = clean_dataframe_column_names(pl.read_csv(file_path))
    _validate_point_columns(dataframe)

    points = [
        SpecialPoint(
            id=int(row["No."]),
            name=str(row["Data point name"]),
            x=float(row["x_coord"]),
            y=float(row["y_coord"]),
            z=float(row["z_coord"]),
        )
        for row in dataframe.iter_rows(named=True)
    ]

    for point in points:
        if not all(isfinite(value) for value in (point.x, point.y, point.z)):
            raise ValueError(
                f"Point {point.id} has a non-finite coordinate or elevation"
            )

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
    return [
        SpecialPoint(
            id=point.id,
            name=point.name,
            x=point.x - min_x,
            y=point.y - min_y,
            z=point.z,
            outer_polygon=point.outer_polygon,
        )
        for point in points
    ]


def clean_dataframe_column_names(df: pl.DataFrame) -> pl.DataFrame:
    """Remove extra spaces from CSV column names."""
    return df.rename({column: column.strip() for column in df.columns})


def _validate_point_columns(dataframe: pl.DataFrame) -> None:
    missing = [
        column for column in REQUIRED_POINT_COLUMNS if column not in dataframe.columns
    ]
    if missing:
        raise ValueError("CSV is missing required column(s): " + ", ".join(missing))
