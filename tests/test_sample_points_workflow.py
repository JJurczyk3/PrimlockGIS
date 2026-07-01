from pathlib import Path

from primelock_gis.app.sample_points_workflow import render_sample_points_from_csv


def test_render_sample_points_from_csv_returns_terminal_frame():
    output = render_sample_points_from_csv(
        Path("data/initial_coords.csv"),
        view_width=30,
        view_height=12,
    )

    assert isinstance(output, str)
    assert len(output.splitlines()) == 12
