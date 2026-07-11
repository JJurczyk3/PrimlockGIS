# Primelock GIS

Primelock GIS is a lightweight terminal-based GIS prototype for an Advanced GIS coursework project. It is written in Python and intentionally implements the core GIS algorithms directly instead of using external GIS libraries.

The current application works with sampled point data, builds interpolation grids and TIN models, renders terrain and contour layers in a terminal viewer, and provides a second-terminal support panel for inspection and runtime control.

## Current Features

- CSV dataset loading and coordinate normalization from `data/initial_coords.csv` or a user-provided CSV.
- `ProjectConfig` and safe project rebuild flow for dataset reloads and grid-division changes.
- Regular grid generation from sample points.
- IDW interpolation as the default grid interpolation method.
- Directional weighted-average interpolation in the core/grid builder path.
- Grid densification by bilinear subdivision.
- Bowyer-Watson / Delaunay-style TIN generation from sample points.
- Grid contour segment generation, tracing, labels, and rendering.
- TIN contour segment generation, tracing, labels, and rendering.
- Terrain coloring from the selected contour source, using either grid or TIN values as terminal background colors.
- Terrain palette and simulated opacity controls.
- First-pass node/arc/polygon topology construction from linework and traced contours.
- Table-like topology export helpers.
- Interactive terminal viewer with pan, zoom, layer toggles, feature selection, and status rows.
- Support/control panel in a second terminal with layer controls, model controls, dataset reload, and admin commands.

## Requirements

- Python 3.13+
- `uv`
- Runtime dependency: `polars`
- Development/test dependency: `pytest`

Install and run through `uv`; no separate GIS packages are required.

## Teacher Quick Start

1. Install Python 3.13 or newer.
2. Install `uv`.
3. Extract the submitted ZIP file.
4. Open a terminal in the extracted `PrimlockGIS` folder.
5. Run:

```bash
uv run pytest
```

To run the interactive program, open two terminal windows in the project folder.

Terminal 1:

```bash
uv run python -m primelock_gis viewer
```

Terminal 2:

```bash
uv run python -m primelock_gis support
```

The viewer and support panel communicate on `127.0.0.1:8765`.

## Platform Notes

- Linux and macOS: use a normal terminal with ANSI escape support.
- Windows: use Windows Terminal or PowerShell. Kitty is not required. The program includes a Windows console input path; mouse support depends on the terminal, but keyboard controls and support-panel commands are available.
- If `uv` is not installed, install it with `python -m pip install uv` on Linux/macOS or `py -m pip install uv` on Windows.
- If the terminal asks about firewall/network access, allow local connections for `127.0.0.1`.
- For offline standalone builds, see `PACKAGING.md`.

## Run

Start the viewer:

```bash
uv run python -m primelock_gis viewer
```

Start the support/control panel in a second terminal:

```bash
uv run python -m primelock_gis support
```

Run tests:

```bash
uv run pytest
```

## Final Assignment Checklist

- Executable program: run `uv run python -m primelock_gis viewer`; open a second terminal and run `uv run python -m primelock_gis support`.
- Printed source code: include `src/primelock_gis`, `tests`, `README.md`, `PACKAGING.md`, `design.md`, `pyproject.toml`, and `data/initial_coords.csv`.
- Printed run result: include the viewer/support-panel screenshots or terminal output, plus `uv run pytest` output.
- Downloadable file: submit `PrimelockGIS-submission.zip` or the standalone package described in `PACKAGING.md`.

## Viewer Controls

- `q`: quit viewer
- `h` / `j` / `k` / `l`: pan
- `+` / `-`: zoom
- Mouse drag: pan
- Mouse wheel: zoom
- Mouse click: select the nearest visible feature
- `r`: reset viewport
- `p`: toggle points
- `b`: toggle terrain coloring
- `g`: toggle grid
- `t`: toggle TIN
- `c`: toggle contours
- `m`: switch contour source between grid and TIN
- `v`: toggle contour labels

## Support Panel

The support panel talks to the viewer over a local command socket.

Tabs:

- `Info`: selected feature details.
- `Layers`: clickable toggles for points, terrain, grid, TIN, contours, contour source, labels, terrain opacity, and terrain palette.
- `Model`: grid division stepper controls, typed X/Y grid division inputs, and presets.
- `Dataset`: current dataset/config summary and reload button.
- `Admin`: typed commands and viewer lifecycle controls.

Useful support/admin commands:

```text
summary
model summary
config
layers summary
selected feature
set grid 30 30
load dataset data/initial_coords.csv
reload dataset
toggle terrain
toggle grid
toggle tin
toggle points
toggle contours
toggle contour source
toggle contour labels
contour source grid
contour source tin
contour interval 25
contour summary
terrain opacity 0.7
terrain palette heat
terrain summary
query grid <row> <col>
quit viewer
```

Failed dataset loads are handled safely: the current project remains visible and active if the replacement dataset cannot be loaded or rebuilt.

## Data Format

CSV input is expected to include these columns:

```text
No.,Data point name,x_coord,y_coord,z_coord
```

The included coursework dataset has 43 sample points.

## Project Layout

- `src/primelock_gis/core`: geometry, models, algorithms, loading, topology export.
- `src/primelock_gis/core/rendering`: scene objects, symbology, viewport, scene builders.
- `src/primelock_gis/ui/terminal`: terminal canvas, renderer, interactive viewer, support panel.
- `src/primelock_gis/app`: project config/state, rebuild service, startup workflow.
- `tests`: unit tests for algorithms, rendering, input, viewer commands, and support panel behavior.
