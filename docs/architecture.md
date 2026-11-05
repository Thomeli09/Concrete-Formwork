# Architecture (v0.2.0)

## Separation of concerns

```text
Shapely Formwork + SoilRegion / Brace             Concrete
                │                                    │
                └─────────── PouringSimulation ───────┘
                                   │
             per-Pour pressure law (PressureLaw protocol)
             Hydrostatic, Capped, Power, Tabulated, Callable
                                   │
                    wall-specific optional modifier
                    (wall, s, base_p) -> Pa
                                   │
                         WallPressureProfile
                    ordered (s_m, pressure_Pa)
                                   │
                   adaptive quadrature over knots
                 ∫p ds, ∫s*p ds, resultant, center
                    │                       │
                CSV export             section.py layers
                                            │
                              generic plot_2d.py & plot_basic.py
                                            │
                                  Matplotlib Axes artists
```

The pressure model is independent of Matplotlib and does not assume a linear
profile. Each straight wall is parameterized by curvilinear distance `s`
from its `Wall.start` to `Wall.end`. The value returned for each point is the
sum of the selected pours' contributions, potentially transformed by a
wall-local function.

### Why integrate separately from drawing samples?

A polynomial pressure such as `p(s)=1000*s**2` cannot be integrated
accurately by connecting two endpoint values with a straight line.
`wall_loads(samples_per_wall=2)` can intentionally return only two
visualization samples but still calculate an accurate force and center of
pressure with adaptive Simpson integration. Users may control display nodes
with `nodes_by_wall={index: [s1, s2, ...]}`. Concrete layer and constitutive
breakpoints are *also* included automatically, ensuring that piecewise models
are integrated across separate branches.

### Stability assumptions

- All pressures are gauge, scalar, nonnegative and directed along the outward
  unit normal on the wetted wall face. Forces always integrate over the
  out-of-plane formwork width.
- Each law receives its layer's `depth` (capped to that layer's height),
  physical layer height, and concrete unit weight. Contributions below a layer
  are saturated and passed to the lower formwork surface.
- Pressure laws are mathematical options, **not standards-based concrete
  setting, consolidation, or rheological models**.
- The cavity, concrete regions and physical wall geometry are immutable;
  stages append pours rather than replacing existing geometry.
- The soil/bracing models are 2D drawings only and have no mechanical
  connectivity to the pressure solver.

### Extending pressure

For arbitrary layer laws, implement `PressureLaw.pressure(depth, *, height,
unit_weight) -> Pa` and `break_depths(*, height, unit_weight) -> tuple[m,...]`,
or use `CallablePressure(function, knots=...)`. For arbitrary wall-local laws,
use `wall_pressure_function(wall, s, base_pressure) -> Pa` at simulation creation.
For discontinuous/non-smooth custom pressure, supply knots where the expression
changes, check convergence, and compare against reference cases. A future
finite-element/continuum solver could emit wall pressure functions or profile
samples without changing the visualization layer.

### Testing

The test suite includes linear hydrostatic forces/centers, exact polynomial
integrals for quadratic distributions, capped pressure changes, measured
piecewise triangles, per-pour additive selections, wall-local corrections,
user-defined sampling nodes, Shapely polygon holes, and headless independent
plotting. The package still needs external engineering validation before use
for structural design.
