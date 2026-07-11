# Primelock GIS Design Notes

This document describes the current implementation structure and the remaining
hardening work for the coursework application.

## Architecture

Primelock GIS is organised into five practical layers.

### CLI and application coordination

- `primelock_gis/__main__.py` defines the public `viewer`, `support`, `launch`,
  `doctor`, and `--version` commands.
- `app/project_state.py` owns `ProjectConfig` and the current computed
  `ProjectState`.
- `app/project_builder.py` loads a dataset and constructs its interpolation
  grid and TIN. Its safe rebuild path keeps the previous project active if a
  replacement cannot be built.
- `app/startup.py` resolves the bundled dataset, creates the initial viewport,
  starts the local command server, and runs the viewer.

### GIS domain models and algorithms

- `core/models` contains grids, TINs, contours, and vector feature models.
- `core/algorithms` contains interpolation, grid construction and
  densification, TIN generation, contour extraction/tracing, and topology
  processing.
- `core/load_data.py`, `core/geometry.py`, and `core/storage` provide dataset,
  geometry, and topology-export support.

This layer contains the GIS work independently of terminal or Windows launch
details.

### Rendering

- `core/rendering` defines backend-independent scenes, drawable objects,
  symbology, scene builders, viewport transforms, and the renderer interface.
- `ui/terminal/renderer2d.py` projects those drawables into terminal cells.
- `ui/terminal/canvas.py` combines foreground/background colour, Unicode line
  characters, and Braille sub-cells into the final text frame.

### Terminal platform and user interface

- `ui/terminal/events.py` defines normalized key, mouse, and resize events.
- `ui/terminal/session.py` owns alternate-screen, cursor, mouse, and cleanup
  behavior shared by all platforms.
- `ui/terminal/backends/posix.py` preserves the macOS/Linux cbreak and VT input
  path. `backends/windows.py` uses native Win32 console records while retaining
  ANSI/virtual-terminal output.
- `ui/terminal/interactive_app.py` coordinates the viewer, visible layers,
  viewport interaction, feature selection, scene caching, and support
  commands.
- `ui/terminal/support_panel.py` provides the second-terminal control panel and
  a localhost command channel that supports per-launch authentication.

### Launch and packaging

- `app/launcher.py` resolves source/frozen runtime paths, chooses a free
  loopback port and per-launch identity, and opens the viewer and support panel
  in Windows Terminal or ordinary console windows.
- `packaging/pyinstaller` defines the Windows console-mode frozen application.
- `packaging/runtime` contains the professor-facing launch templates.
- `tools/build_standalone.py` assembles the portable runtime and release ZIP.

The portable launcher is Windows-specific, but the source viewer retains its
POSIX terminal backend for macOS and Linux.

## Data and Control Flow

The primary GIS data path is:

```text
CSV dataset
  -> normalized sample points
  -> ProjectConfig + project builder
  -> ProjectState (points, interpolation grid, TIN)
  -> contour/terrain/layer scene builders
  -> backend-independent Scene
  -> TerminalRenderer2D
  -> TerminalCanvas
  -> ANSI, Unicode, and Braille frame
```

Grid or TIN contours are derived lazily from the current project and viewer
settings. Dataset changes and grid-division changes build a replacement
`ProjectState`; the viewer swaps it in only after the rebuild succeeds.

The interactive control path is:

```text
POSIX VT input or Windows console records
  -> TerminalSession platform backend
  -> KeyEvent / MouseEvent / ResizeEvent
  -> viewer or support controller
  -> state/viewport change
  -> dirty-frame render
```

For one-click Windows launch, the launcher passes the same free localhost port
and random session identity to both child processes. The viewer binds only to
`127.0.0.1`. A socket handler authenticates each request and places it on the
viewer's command queue; the viewer executes it in its event loop and returns
the result through a reply queue. The support panel retries while the viewer is
starting and displays a waiting state instead of treating startup delay as an
immediate failure.

## Completed

- CSV point loading and column cleanup.
- Coordinate normalization for display and modeling.
- Basic geometry utilities.
- Viewport transforms, pan, zoom, and resize behavior.
- Terminal canvas with foreground colors, background colors, line merging, Unicode and ASCII fallbacks, and Braille line support.
- Terminal renderer for points, grid lines, TIN edges, contours, labels, topology linework, and terrain color backgrounds.
- Scene builders for points, grids, TINs, contours, topology, and terrain.
- Regular grid model generation.
- IDW interpolation.
- Directional weighted-average interpolation in core grid generation.
- Grid densification by bilinear subdivision.
- Bowyer-Watson / Delaunay-style TIN generation.
- Grid contour generation and tracing into open/closed polylines.
- TIN contour generation and tracing.
- Contour label scene generation.
- Terrain coloring from the selected contour source using grid or TIN values.
- Terrain palette controls and simulated terrain opacity by color blending.
- First-pass node/arc/polygon topology from point sequences and contour polylines.
- Table-like topology export helpers.
- Interactive terminal viewer with keyboard and mouse controls.
- Support/control panel in a second terminal.
- Runtime commands for layer toggles, contour settings, grid divisions, terrain style, dataset load/reload, config summary, and model summary.
- Support-panel typed grid division controls for larger grid sizes.
- Safe project rebuild path that keeps the current project if a dataset load or rebuild fails.

## Known Limitations

- Directional interpolation is implemented in core and supported by `ProjectConfig`, but the viewer/support panel does not yet expose a runtime interpolation-method control.
- Project rebuilds are structured behind a service, but expensive rebuilds still run synchronously.
- Terrain coloring is implemented as a terminal background layer, but there is no low-resolution panning mode or delayed high-resolution redraw yet.
- Topology construction handles endpoints, intersections, arcs, and simple closed-ring polygons, but it is still a first pass and needs more validation on complex contour networks.
- Topology export returns table-like Python records; file export formats are not yet formalized.
- Support panel uses typed admin commands for dataset paths; there is no interactive path input widget yet.
- Error messages are practical but not yet centralized.
- The viewer and support controllers still combine several UI responsibilities;
  further module separation is desirable, but is not required for the current
  runtime.
- Full mouse behavior depends on terminal-emulator support. A Windows console
  that cannot enable mouse records reports a keyboard-only diagnostic.
- The support channel is deliberately local to one machine and is not a remote
  or multi-user service.

## Next Priority

1. Add runtime interpolation-method controls:
   - `set interpolation idw`
   - `set interpolation directional`
   - support-panel model control display
   - rebuild through the existing project rebuild service

2. Move project rebuilds to a background worker:
   - support panel requests a change
   - viewer keeps rendering the old model
   - status shows loading/rebuilding
   - successful worker result swaps in the new `ProjectState`
   - failed worker result preserves the old `ProjectState`

3. Harden topology:
   - polygon orientation and adjacency validation
   - duplicate/near-duplicate node tolerance review

4. Improve dataset workflow:
   - support-panel path entry
   - clearer validation for missing columns and malformed CSV rows
   - recent dataset path display

## Future Work

- General layer opacity beyond the terrain background layer.
- Terrain low-resolution mode while panning and full-resolution redraw after interaction stops.
- Contour smoothing.
- Topology file export.
- Additional layer controls for ordering and styling.
- More robust large-dataset performance profiling.
- Optional GUI front end after the terminal workflow and algorithms are stable.

## Current Data

The included dataset is `data/initial_coords.csv`, with 43 sampled points and columns:

```text
No.,Data point name,x_coord,y_coord,z_coord
```

Coordinates are normalized for display by shifting x/y so the minimum x and y become zero. Original z values are preserved.
