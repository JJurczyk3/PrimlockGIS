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
- Terrain coloring from grid values as terminal background colors.
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

## Run

Start the viewer:

```bash
uv run python -m primelock_gis viewer
```

Start the support/control panel in a second terminal:

```bash
uv run python -m primelock_gis support
```

Render the contour demo script:

```bash
uv run python scripts/render_contours_demo.py --show-grid
```

Run tests:

```bash
uv run pytest
```

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
- `[` / `]`: decrease/increase contour interval

## Support Panel

The support panel talks to the viewer over a local command socket.

Tabs:

- `Info`: selected feature details.
- `Layers`: clickable toggles for points, terrain, grid, TIN, contours, contour source, and labels.
- `Model`: grid division controls and presets.
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
- `scripts`: small command-line demos.
- `tests`: unit tests for algorithms, rendering, input, viewer commands, and support panel behavior.
