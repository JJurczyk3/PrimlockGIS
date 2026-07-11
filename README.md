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

## Source Development Requirements

- Python 3.13+
- `uv`
- Runtime dependency: `polars`
- Build dependencies are declared in the `dev` dependency group.

Install and run through `uv`; no separate GIS packages are required.

## Teacher Quick Start

For the portable Windows submission:

1. Extract the complete `PrimelockGIS-Windows-x64-v0.1.1.zip` file.
2. Open the extracted `PrimelockGIS-Windows-x64-v0.1.1` folder.
3. Double-click `START_PRIMELOCK_GIS.bat` for English, or
   `启动_PRIMELOCK_GIS_中文版.bat` for Simplified Chinese.

The viewer and Support / Control panel open automatically and connect over a
private localhost session. The portable package does not require Python, `uv`,
PowerShell policy changes, administrator access, or internet access.

An optional `PrimelockGIS-Windows-x64-Setup-v0.1.1.exe` is also available. It
installs the same offline runtime for the current user, adds a Start menu
shortcut for each language, offers optional English/Chinese desktop shortcuts,
and includes an uninstaller.
The portable ZIP remains the primary submission and fallback. The source ZIP
contains the reviewable application source, documentation, data, and build
definitions; it is not a standalone runtime.

To run the source version manually, open two terminal windows in the project folder.

Terminal 1:

```bash
uv run python -m primelock_gis viewer
```

Terminal 2:

```bash
uv run python -m primelock_gis support
```

For the Simplified Chinese source interface, add `--language zh-CN` after either
mode:

```bash
uv run python -m primelock_gis viewer --language zh-CN
uv run python -m primelock_gis support --language zh-CN
```

Manual source modes default to `127.0.0.1:8765`. The one-click launcher selects
a free localhost port and gives both processes the same per-launch identity.

## Platform Notes

- Linux and macOS: use a normal terminal with ANSI escape support.
- Windows: the one-click launcher prefers two titled Windows Terminal tabs and falls back to two ordinary console windows. Kitty is not required.
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

## Final Assignment Checklist

- Executable program: extract the Windows runtime ZIP and double-click `START_PRIMELOCK_GIS.bat`.
- Complete source: submit the versioned source ZIP containing the application,
  documentation, data, and build/packaging files.
- Printed source: generate the curated GIS-first copy described in
  `COURSEWORK_SOURCE_GUIDE.md`; it complements rather than replaces the source
  ZIP.
- Printed run result: include the viewer/support-panel screenshots or terminal output requested by the coursework brief.
- Downloadable files: submit the versioned Windows runtime and source ZIPs described in `PACKAGING.md`.

## Printed Source Submission

The complete source ZIP is the authoritative electronic submission. It keeps
the application code, documentation, sample data, and release tooling needed
for review and reproducible builds.

The paper/PDF source copy is intentionally curated and GIS-first. It presents
the project architecture, data models, algorithms, rendering pipeline, and
representative application/platform integration without printing thousands of
lines of repetitive terminal layout or operating-system plumbing. It is not a
standalone build and must not be used as a substitute for the complete source
ZIP.

The English selection rationale is in
[`COURSEWORK_SOURCE_GUIDE.md`](COURSEWORK_SOURCE_GUIDE.md). The final physical
submission uses the Chinese introduction and AI-use disclosure in
[`COURSEWORK_SOURCE_GUIDE_ZH.md`](COURSEWORK_SOURCE_GUIDE_ZH.md), followed by
the GIS-first code listing with translated comments and docstrings. Build the
versioned, A4 PDF with:

```bash
uv run python tools/build_chinese_submission_report.py
```

The result is written to `output/pdf/PrimelockGIS-中文源代码报告-v<version>.pdf`.
Python identifiers, APIs, protocol tokens, and runtime strings remain
unchanged; only the printed explanatory prose is translated. The older
[`tools/build_printed_source.py`](tools/build_printed_source.py) remains
available for the standalone English HTML copy.

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
- `src/primelock_gis/ui/terminal`: terminal platform backends, canvas, renderer, interactive viewer, and support panel.
- `src/primelock_gis/app`: project config/state, rebuild service, startup workflow, resource resolution, and Windows launch orchestration.
- `packaging` and `tools`: PyInstaller configuration, runtime launch templates, and release/submission builders.
