# Primelock GIS Coursework Source Guide

This guide is the entry point for reviewing the Primelock GIS source code.

## Project identity

- Application and executable name: **Primelock GIS** / `PrimelockGIS.exe`
- Python import package: `primelock_gis`
- Distribution metadata name: `primlockgis` (retained for compatibility)
- Release version: read from `pyproject.toml`

## Processing flow

```text
CSV sample points
    -> schema validation and numeric loading
    -> x/y origin normalisation
    -> ProjectConfig
    -> regular interpolation grid + TIN
    -> grid or TIN contours
    -> optional first-pass topology
    -> backend-independent scene and viewport
    -> terminal renderer and viewer/support controls
```

`ProjectConfig` is the input to project construction. `ProjectState` groups the
validated points and derived grid and TIN so the viewer cannot accidentally
combine models from different datasets. A failed reload returns the old state
unchanged.

## Requirements traceability

| Coursework capability | Primary implementation |
| --- | --- |
| CSV loading and field validation | `core/load_data.py` |
| Point/vector data models | `core/models/vector.py` |
| IDW interpolation | `core/algorithms/interpolation.py` |
| Directional interpolation | `core/algorithms/interpolation.py` |
| Regular-grid generation and densification | `core/algorithms/grid.py`, `core/models/grid.py` |
| TIN generation and sampling | `core/algorithms/tin.py`, `core/models/tin.py` |
| Grid and TIN contour extraction | `core/algorithms/contour.py` |
| Contour tracing | `core/algorithms/contour.py`, `core/models/contour.py` |
| First-pass topology | `core/algorithms/topology.py` |
| Viewport and scene conversion | `core/rendering` |
| Terminal rendering | `ui/terminal/canvas.py`, `renderer2d.py` |

Paths in this table are relative to `src/primelock_gis`.

## GIS methods and assumptions

### Coordinates and elevation

The loader requires identifier, name, x, y, and z columns. It rejects missing
or non-finite coordinate values. Normalisation subtracts the minimum x and y
from every point and preserves z. This is a local origin shift only: the code
does not infer a coordinate reference system, change units, perform a datum
transformation, or alter elevation values. Therefore, distances, areas, contour
intervals, and elevations retain the units of the input dataset.

### Inverse-distance weighting

For a target position, IDW computes

```text
z(target) = sum(w_i * z_i) / sum(w_i), where w_i = 1 / d_i^2
```

An exact sample-position match returns that sample's elevation directly. The
implementation uses every input point, a fixed power of 2, and no search
radius. These choices are visible in `idw_value` rather than hidden in UI code.

### Directional weighted average

The full circle around the target is divided into equal angular sectors. The
nearest sample in each non-empty sector is selected, then the same inverse-
distance-square calculation is applied to those samples. This reduces the
influence of clustered observations from one direction. The default is four
sectors (one per quadrant).

### Regular grid

`x_divisions` and `y_divisions` describe cells, so the stored node array has one
more row and column than the division counts. Node coordinates are evenly
spaced over the sample extent. Grid construction requires positive divisions
and a finite, non-zero extent in both axes. Densification divides each source
cell and obtains new node elevations by bilinear interpolation.

### TIN

The TIN builder uses incremental Bowyer-Watson triangulation:

1. Create a super-triangle around all samples.
2. Insert each sample vertex.
3. Remove triangles whose circumcircle contains that vertex.
4. Re-triangulate the resulting boundary.
5. Remove triangles connected to the artificial super-triangle.
6. Attach neighbouring-triangle identifiers across shared edges.

Input coordinates and elevations must be finite. TIN points require unique x/y
positions and at least three non-collinear samples. Elevation inside a triangle
is obtained from barycentric coordinates.

### Contours

Grid contours examine the four edges of each cell. A crossing is linearly
interpolated when endpoint elevations straddle the level. A four-crossing
ambiguous cell is resolved using its mean centre elevation. TIN contours apply
the same edge-crossing rule to each triangle. Shared edge keys then connect raw
segments into open or closed polylines. Values exactly equal to a contour level
receive a deterministic perturbation of `interval / 5000` to avoid vertex
singularities.

### Topology

The first topology pass removes consecutive duplicates, detects segment
intersections, splits linework, creates shared nodes and arcs, and creates a
simple polygon record for eligible closed sequences. The tolerance defaults to
the geometry module's `EPS`. Collinear overlaps, holes, complex polygon
validation, and full planar enforcement are deliberately outside this first
pass.

### Rendering

GIS algorithms create models; scene builders convert models to drawable
objects; the viewport maps world coordinates to screen coordinates. The
terminal renderer then draws ANSI colour, Unicode lines, and Braille detail.
Keeping these stages separate prevents terminal interaction code from becoming
mixed with the GIS calculations.

## Printed order

The main printed body is ordered as follows:

1. This guide and the generated manifest.
2. Data loading and geometry primitives.
3. Vector, grid, TIN, and contour models.
4. Interpolation, grid, TIN, contour, and topology algorithms.
5. UI, platform-integration, and packaging code remains in the electronic
   source and is omitted from the physical booklet.

Generate it from the repository root with:

```text
uv run python tools/build_printed_source.py
```

Open the resulting versioned HTML in a browser and print with a Unicode-capable
monospace font. The generator supplies line numbers, file headings, page breaks,
and print CSS. Browser headers and footers may be disabled in the print dialog.

## Complete source versus printed copy

The printed copy is deliberately limited to the assessed GIS functions. It
does not repeat large terminal layouts, complete Win32 declarations, or
packaging logic. The versioned source ZIP contains the production source,
build scripts, configuration, lockfile, notices, and bundled dataset.

## Known limitations

- Bowyer-Watson output near duplicate or co-circular points is governed by a
  small fixed numerical tolerance.
- TIN model lookup caches assume geometry is not mutated after construction.
- Topology processing is a documented first pass and does not resolve
  collinear overlaps or polygon holes.
- Large model rebuilds currently run synchronously.
