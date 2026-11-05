# Architecture and extension guide

The old `GeometryLib`, `ElementLib`, `LoadingLib`, `MaterialLib`, and generic
plotting helpers are intentionally **not included**. The revised package has
one explicit responsibility: filling a Shapely-based 2D formwork cavity and
calculating hydrostatic loads from the resulting concrete layers.

## Data flow

```text
Formwork.from_profile(...) ───┐
                              ├─> Formwork.cavity: shapely.Polygon
Formwork.from_polygon(...) ───┘       │
                                     ├─> filled_region(elevation)
                                     ├─> volume_at(elevation)
                                     └─> walls (coordinates + outward normals)
                                             │
Concrete(name, unit_weight) ───┐              │
                               ├─> PouringSimulation
Sequential level/volume pours ┘       │
                                      ├─> Pour.region (Shapely difference)
                                      ├─> stage-specific filled volume
                                      ├─> hydrostatic_pressure(z)
                                      ├─> wall_loads() (analytic integration)
                                      └─> summary(stage)
                                               │
                              ┌────────────────┴────────────────┐
                         plot_section(...)                wall_load_records(...)
                         plot_pressure_profile(...)       export_wall_loads_csv(...)
```

## Core invariants

1. Coordinates use metres, `(x, z)`. The cavity must be a valid polygon with
   positive area. There is no custom geometry engine.
2. `Formwork.from_profile` requires two distinct endpoints at the **same
   uppermost elevation** and introduces an implicit non-structural top edge.
   `Formwork.from_polygon` accepts a closed polygon and its holes directly.
3. Pours are appended sequentially. No pour overlaps earlier concrete in area.
   An over-rim level is clipped to the cavity top (not treated as overflow).
4. Each pressure-bearing wall is stored as a straight segment with a normal
   pointing **out of the concrete**, invariant to the input vertex order.
5. Pressure is computed per material **in N/m²**, proportional to unit weight
   **in N/m³**. Individual wall forces are in N for the full section width.
6. Wall segments are subdivided at concrete interfaces and the free surface,
   so the pressure integral and application point are analytical rather than
   estimated by plotting resolution.
7. The computational core depends only on Shapely, with no Matplotlib global
   state. Rendering returns a Matplotlib `(Figure, Axes)` without calling show.
8. Every staged summary is immutable. The simulation can only grow by adding
   another pour; prior stage outputs remain reproducible.

## Next extensions

- **Time evolution:** separate placement events from instantaneous stage state;
  introduce curing, concrete age, pump rate, and wall pressure envelope models.
- **Fresh vs set material:** add an explicit pressure model interface and a
  state variable per layer. Do not emulate set concrete by simply deleting its
  hydrostatic contribution: transmission of stress and structural support would
  have to be modelled.
- **Structural checks:** define formwork supports and members separately; do
  not equate hydrostatic loads with capacity assessment or standard compliance.
- **Topology:** model gravity-driven access to disconnected recesses rather
  than prescribing a shared free-surface elevation for all components.
- **3D geometry:** use solids/meshes instead of multiplying section area by a
  fixed width; Shapely itself is predominantly planar.

## Testing

`pytest` checks a rectangle against closed-form results (area, volume,
triangular wall loading and center of pressure), stepped/concave polygons,
polygon holes, stage selection, differing material unit weights, over-rim
clipping, invalid inputs, and headless plotting/CSV smoke tests. Compare any
future pressure model to appropriate experimental or standards-based benchmarks.
