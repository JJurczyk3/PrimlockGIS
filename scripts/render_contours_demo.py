"""Render a terminal demo of grid-generated contours."""

from argparse import ArgumentParser
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from primelock_gis.core.algorithms.contour import (
    contour_segments_from_grid,
    generate_contour_levels,
    grid_value_range,
    trace_contour_segments,
)
from primelock_gis.core.algorithms.grid import create_grid_model_idw, densify_grid_model
from primelock_gis.core.algorithms.topology import build_topology_from_contour_polylines
from primelock_gis.core.load_data import load_normalised_sample_points
from primelock_gis.core.rendering.scene import Scene
from primelock_gis.core.rendering.scene_builder import (
    contour_polylines_to_scene,
    grid_to_scene,
    points_to_scene,
)
from primelock_gis.core.rendering.symbology import PointStyle, PolylineStyle
from primelock_gis.core.rendering.viewport_builder import initial_viewport_from_points
from primelock_gis.ui.terminal.capabilities import detect_terminal_capabilities
from primelock_gis.ui.terminal.render_app import TerminalRenderApp


def main() -> None:
    args = parse_args()
    points = load_normalised_sample_points(args.csv)

    grid = create_grid_model_idw(
        points,
        x_divisions=args.grid_divisions,
        y_divisions=args.grid_divisions,
    )

    if args.densify > 1:
        grid = densify_grid_model(
            grid,
            x_splits=args.densify,
            y_splits=args.densify,
        )

    min_z, max_z = grid_value_range(grid)
    levels = generate_contour_levels(min_z, max_z, args.interval)
    segments = contour_segments_from_grid(grid, levels, args.interval)
    polylines = trace_contour_segments(segments, grid)
    topology = build_topology_from_contour_polylines(polylines)
    scene = build_scene(grid, polylines, points, show_grid=args.show_grid)

    terminal_size = shutil.get_terminal_size((120, 45))
    viewport = initial_viewport_from_points(
        points,
        view_width=terminal_size.columns,
        view_height=max(20, terminal_size.lines - 8),
        padding=0.05,
    )

    render_app = TerminalRenderApp(
        scene=scene,
        viewport=viewport,
        capabilities=detect_terminal_capabilities(),
    )

    print_summary(
        point_count=len(points),
        grid_x_divisions=grid.x_divisions,
        grid_y_divisions=grid.y_divisions,
        levels=levels,
        segment_count=len(segments),
        polylines=polylines,
        topology_node_count=len(topology.nodes),
        topology_arc_count=len(topology.arcs),
        topology_polygon_count=len(topology.polygons),
        min_z=min_z,
        max_z=max_z,
    )
    print()
    print(render_app.redraw())


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/initial_coords.csv"),
        help="CSV file containing coursework sample points.",
    )
    parser.add_argument(
        "--grid-divisions",
        type=int,
        default=20,
        help="Base IDW grid divisions in x and y.",
    )
    parser.add_argument(
        "--densify",
        type=int,
        default=2,
        help="Subdivisions per base grid cell. Use 1 to disable densification.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=50.0,
        help="Contour interval.",
    )
    parser.add_argument(
        "--show-grid",
        action="store_true",
        help="Render the interpolation grid behind the contours.",
    )
    return parser.parse_args()


def build_scene(grid, polylines, points, show_grid: bool) -> Scene:
    scene = Scene()

    if show_grid:
        merge_scene(
            scene,
            grid_to_scene(
                grid,
                style=PolylineStyle(
                    color="#334155",
                    char=".",
                    line_type="solid",
                ),
            ),
        )

    merge_scene(
        scene,
        contour_polylines_to_scene(
            polylines,
            style=PolylineStyle(
                color="#7DD3FC",
                char="=",
                line_type="solid",
            ),
        ),
    )
    merge_scene(
        scene,
        points_to_scene(
            points,
            style=PointStyle(
                color="#FACC15",
                char="●",
            ),
        ),
    )
    return scene


def merge_scene(target: Scene, source: Scene) -> None:
    target.polygons.extend(source.polygons)
    target.polylines.extend(source.polylines)
    target.points.extend(source.points)
    target.texts.extend(source.texts)


def print_summary(
    point_count: int,
    grid_x_divisions: int,
    grid_y_divisions: int,
    levels: list[float],
    segment_count: int,
    polylines,
    topology_node_count: int,
    topology_arc_count: int,
    topology_polygon_count: int,
    min_z: float,
    max_z: float,
) -> None:
    open_count = sum(1 for polyline in polylines if not polyline.closed)
    closed_count = sum(1 for polyline in polylines if polyline.closed)

    print(f"Input points: {point_count}")
    print(f"Grid divisions: {grid_x_divisions} x {grid_y_divisions}")
    print(f"Grid z range: {min_z:.2f} to {max_z:.2f}")
    print(f"Contour levels: {format_levels(levels)}")
    print(f"Raw contour segments: {segment_count}")
    print(f"Traced contour polylines: {len(polylines)}")
    print(f"Open contours: {open_count}")
    print(f"Closed contours: {closed_count}")
    print(f"Topology nodes: {topology_node_count}")
    print(f"Topology arcs: {topology_arc_count}")
    print(f"Topology polygons: {topology_polygon_count}")


def format_levels(levels: list[float]) -> str:
    if not levels:
        return "none"

    return ", ".join(f"{level:g}" for level in levels)


if __name__ == "__main__":
    main()
