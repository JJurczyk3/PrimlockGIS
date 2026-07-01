# Primelock GIS Design Notes

This document tracks the current implementation state and near-term roadmap for the coursework prototype.

## Architecture

Primelock GIS is split into four layers:

- `core/models`: data models for points, grids, TINs, contours, and topology.
- `core/algorithms`: interpolation, grid construction, grid densification, TIN generation, contour extraction/tracing, topology construction.
- `core/rendering`: backend-independent scene objects, styles, viewport transforms, and scene builders.
- `ui/terminal`: terminal canvas, ANSI rendering, input parsing, interactive viewer, and support panel.

The terminal UI should call app/core services and scene builders. GIS algorithms should stay in `core`, not in terminal UI modules.

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
- Terrain coloring from grid values using terminal background colors.
- First-pass node/arc/polygon topology from point sequences and contour polylines.
- Table-like topology export helpers.
- Interactive terminal viewer with keyboard and mouse controls.
- Support/control panel in a second terminal.
- Runtime commands for layer toggles, contour settings, grid divisions, dataset load/reload, config summary, and model summary.
- Safe project rebuild path that keeps the current project if a dataset load or rebuild fails.
- Tests for interpolation, grid models, TIN, contours, topology, rendering, terminal input, viewer commands, support panel behavior, config validation, and project rebuild safety.

## Partially Implemented / Needs Hardening

- Directional interpolation is implemented in core and supported by `ProjectConfig`, but the viewer/support panel does not yet expose a runtime interpolation-method control.
- Project rebuilds are structured behind a service, but expensive rebuilds still run synchronously.
- Terrain coloring is implemented as a terminal background layer, but there is no low-resolution panning mode or delayed high-resolution redraw yet.
- Topology construction handles endpoints, intersections, arcs, and simple closed-ring polygons, but it is still a first pass and needs more validation on complex contour networks.
- Topology export returns table-like Python records; file export formats are not yet formalized.
- Contour smoothing is a placeholder.
- Support panel uses typed admin commands for dataset paths; there is no interactive path input widget yet.
- Error messages are practical but not yet centralized.

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
   - more tests for crossing and shared contour networks
   - polygon orientation and adjacency validation
   - duplicate/near-duplicate node tolerance review

4. Improve dataset workflow:
   - support-panel path entry
   - clearer validation for missing columns and malformed CSV rows
   - recent dataset path display

## Future Work

- Layer opacity by simulated color blending against the app background.
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
