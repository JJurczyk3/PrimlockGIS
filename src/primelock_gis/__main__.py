"""Run Primelock GIS."""

from pathlib import Path
import shutil

from primelock_gis.app.sample_points_workflow import render_sample_points_from_csv


def main() -> None:
    terminal_size = shutil.get_terminal_size()
    csv_path = Path("data/initial_coords.csv")

    output = render_sample_points_from_csv(
        csv_path,
        view_width=terminal_size.columns,
        view_height=terminal_size.lines,
    )

    print(output)


if __name__ == "__main__":
    main()