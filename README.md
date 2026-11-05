# Concrete Formwork

[![Python](https://img.shields.io/badge/Python-3.15%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

A **Shapely-backed Python library** for formwork cross-sections, sequential concrete
pours, configurable pressure distributions, numerical wall resultants, and
**composable Matplotlib visualization**. Designed for Python **3.15+**.

**Version 0.2.0** — deliberately new API; no legacy `Node` / `PLine` /
`FormworkLib` compatibility.

## What it does

- Computes areas, physical wall lengths and cross-sectional volumes from a
  Shapely polygon or an open-top formwork profile.
- Places successive concrete pours as independent non-overlapping Shapely
  regions; supports different concrete materials and pressure laws per pour.
- Evaluates pressure on arbitrary **straight wall segments** using wall-local
  curvilinear coordinates `s` (metres) and `pressure` (Pa).
- Computes each wall's **resultant force and center of pressure** using
  adaptive Simpson integration of the selected pressure *function* (not merely
  the sampled display polyline). Automatically adds pour interfaces and
  pressure-law breakpoints, plus user-provided sampling coordinates.
- Keeps a general-purpose `visualization/plot_basic.py`, `plot_2d.py` and
  `plot_parameters.py` layer; `visualization/section.py` calls these primitives.
- Independently draws formwork, a single concrete layer or all layers, the
  pressure from one or multiple pours, wall resultants, soil and bracing.
- Exports wall resultants and sampled wall-pressure coordinates to CSV.

## Units, scope and limitations

- The section uses `(x, z)` in **metres**, with `z` vertically upward; the
  constant out-of-plane width is in metres (**2.5D**, not a 3D solver).
- Unit weight in **N/m³**. Pressure in **Pa**, force in **N**, volume in **m³**.
- `Formwork.from_profile()` closes the cavity with a horizontal *non-physical*
  top edge; `from_polygon()` treats the entire polygon boundary as walls.
- A pour is the region below its chosen horizontal free-surface elevation,
  excluding earlier pours. Over-rim planes are clipped to the cavity top.
  Disconnected pockets are assumed to share the prescribed filling level;
  accessibility or flow into individual pockets is not simulated.
- Pressure laws calculate **additive layer contributions**. Unless customized,
  all concrete is treated as fresh, hydraulically transmitting pressure even
  after a later pour. A lower layer contributes at its full thickness to walls
  beneath its lower interface; the pressure from an upper layer is also
  transmitted to those walls. `pours='Upper'` selects that *contribution*;
  it does **not** mean that pressure acts only along the upper layer's contact
  boundary.
- The alternative capped, power-law, and tabulated distributions are
  **mathematical examples, not implementations of pressure design standards**.
  No concrete hardening, rheological history, pressure decay, pour-rate effects,
  load combinations, bracing stiffness or stability assessment are included.
- Soil and braces are **drawing geometry only**; their constitutive response and
  reactions are not solved.
- Maximum pressure in `summary()` is **sampled** over wall-profile nodes; it is
  not a certified global maximum for arbitrary user-defined functions.
- Adaptive numerical integration is accurate for smooth functions and
  piecewise functions with supplied breakpoints. For jumps, cusps, very sharp
  peaks, or oscillations, declare knots and verify convergence against analytic
  results or refined discretizations. Arbitrary black-box functions are not
  guaranteed to be integrated exactly.

**Engineering use:** Prototype only. The models and numerical outputs are not
independently validated for the design of temporary works. Apply appropriate
engineering standards and verification before using them for safety decisions.

## Install and test

```powershell
# From an extracted copy of this project on Windows:
py -3.15 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
python examples/basic_simulation.py
python examples/composable_layers.py
```

For Linux/macOS use `python3.15 -m venv .venv` and
`source .venv/bin/activate`. Minimal core install: `pip install -e .`;
Matplotlib utilities need `pip install -e ".[plot]"`.

Python 3.15 is the packaging target; the automated tests in this deliverable
were run using Python 3.13 because Python 3.15 was not installed in the
execution environment. The package uses Python >=3.12 type aliases.

## Quick start: geometry and staged concrete

```python
from concrete_formwork import Concrete, Formwork, PouringSimulation

formwork = Formwork.from_profile(
    [(0, 3), (0, 0), (2, 0), (2, 3)], width=1.5,
)

sim = PouringSimulation(formwork)
sim.add_pour_to_level('Base', Concrete('Mix A', unit_weight=24_000), 1.2)
sim.add_pour_to_level('Top', Concrete('Mix B', unit_weight=23_000), 2.6)

print('Area', formwork.area, 'm²')
print('Capacity', formwork.capacity, 'm³')
print('Wall length', formwork.wall_length, 'm')
print('Volume at stage 1', sim.filled_volume(stage=1), 'm³')

for pour in sim.pours:
    print(pour.name, pour.volume, pour.region.geom_type)

result = sim.summary(stage='Top')
print('Total wall-force vector', result.total_force, 'N')
```

For each concrete layer `i`, the region is:

`pour_i.region = cavity_below(top_i) - cavity_below(bottom_i)`

and its volume is `pour_i.region.area * formwork.width`.

## Pressure laws

Built-in examples and a user-defined function:

```python
from concrete_formwork import (
    HydrostaticPressure,
    CappedHydrostaticPressure,
    PowerLawPressure,
    TabulatedPressure,
    CallablePressure,
)

hydro = HydrostaticPressure()  # p = gamma * depth
capped = CappedHydrostaticPressure(maximum_pressure=25_000)
quadratic = PowerLawPressure(exponent=2.0)
measured = TabulatedPressure(((0.0, 0.0), (0.5, 8000.0), (1.5, 14000.0)))
custom = CallablePressure(
    lambda depth, height, unit_weight: unit_weight * depth**2 / height,
    knots=(0.7,),  # optional known internal depths [m]
)

sim = PouringSimulation(formwork)
sim.add_pour_to_level('Base', Concrete('A'), 1.2, pressure_law=quadratic)
sim.add_pour_to_level('Top', Concrete('B'), 2.6, pressure_law=capped)

print(sim.pressure_at(0.0))                 # all contributions, Pa
print(sim.pressure_at(0.0, pours='Top'))   # upper pour's contribution only
print(sim.pressure_at(0.0, stage=1))       # first stage only
```

Each law receives `depth`, `height`, and `unit_weight`. Depth is limited to the
individual pour thickness and is zero above the pour. Each contribution is
summed at the selected stage. `TabulatedPressure.points` contains **depth below
the pour top [m]** and pressure [Pa]; between points, linear interpolation is
used, and beyond the last point the final value is maintained. Provide enough
points to represent your intended profile. A reusable custom law can also
implement the `PressureLaw` protocol (`pressure()` + `break_depths()`).

### Pressure depending directly on the wall coordinate

For pressures varying along the face independently of elevation, optionally
provide `wall_pressure_function`. It receives `(wall, s, base_pressure)` and
returns the replacement pressure [Pa] for that **wall**. This is useful for
spatial corrections or experimental pressure distributions. The passed
`base_pressure` already includes the selected concrete pour contributions.

```python
sim = PouringSimulation(
    formwork,
    wall_pressure_function=lambda wall, s, base: base * (1 + 0.1 * s),
)
```

The wall function operates on wetted formwork only, in `wall_loads()` and
renderings derived from it. `sim.pressure_at(z)` intentionally reports the
base *elevation-only* pressure before this wall-specific correction.

## Wall-local sampling and numerical resultants

Each formwork wall has a unit outward normal and a local length `L`.
`s = 0` is `wall.start`, `s = L` is `wall.end`. **The orientation may be
reordered** when Shapely orients the polygon; always inspect `formwork.walls`
before specifying wall indices and local positions.

```python
for wall in formwork.walls:
    print(wall.index, wall.start, wall.end, wall.length, wall.outward_normal)

loads = sim.wall_loads(
    stage=2,
    pours=['Base', 'Top'],
    samples_per_wall=80,
    nodes_by_wall={0: [0.25, 0.50, 0.83, 1.1]},  # s in metres
)
for load in loads:
    profile = load.profile
    print(profile.wall.index, profile.s, profile.pressure)
    print('Resultant', load.force, 'N; center', load.center_of_pressure, 'm')
```

The paired vectors `profile.s` and `profile.pressure` are ordered along each
wall. `profile.coordinates` converts `s` into global `(x, z)` points. Breaks at
concrete interfaces and pressure-law knots are included automatically.

For a wall width `b` and length `L`:

`F = b * integral_0^L p(s) ds`

`s_R = [integral_0^L s*p(s) ds] / [integral_0^L p(s) ds]`

The resultant vector is `F * outward_normal`. Simpson quadrature integrates
both integrands directly; changing `samples_per_wall` affects *visualization*
resolution, but not the intended integration tolerance. Individual
`WallLoad.pieces` retain interval-wise forces and moments.

## Generic plotting and independent section layers

The supplied generic plotting utilities are included in
`src/concrete_formwork/visualization/`:

- `plot_parameters.py` — reusable `PlotParameters` for styles and axes;
- `plot_basic.py` — figures, axes, legends, colorbars, export;
- `plot_2d.py` — basic lines, text, filled regions, histograms, generic
  `draw_geometry()` for Shapely polygons (including holes) and lines;
- `section.py` — **domain-specific** drawing functions that compose those
  generic primitives. All accept an explicit Matplotlib `Axes` and return
  artists, so individual layers can be updated or removed.

### Manually compose the layers you want

```python
from shapely.geometry import Polygon
from concrete_formwork import Brace, SoilRegion
from concrete_formwork.visualization import (
    PlotParameters, create_figure, configure_axes, save_figure,
    plot_formwork, plot_concrete, plot_pressure, plot_resultants,
    plot_soil, plot_bracing,
)

fig, ax = create_figure()
soil = SoilRegion(Polygon([(-1,-1), (3,-1), (3,0), (-1,0)]))
braces = [Brace.between((0,2), (-1,-1)), Brace.between((2,2), (3,-1))]

plot_soil(ax, soil)                          # soil only
plot_concrete(ax, sim, pours='Base')         # just one region
plot_concrete(ax, sim, pours='Top')          # second concrete region
plot_pressure(ax, sim, pours='Top', show_nodes=True)   # one pour's load
plot_formwork(ax, formwork)                  # formwork walls only
plot_bracing(ax, braces)                     # braces independently
plot_resultants(ax, sim, pours='Top')        # force arrows for this pour

configure_axes(ax, PlotParameters(
    title='Layered formwork', xlabel='x [m]', ylabel='z [m]',
    aspect='equal', show_grid=True,
))
save_figure(fig, 'layered_section.png', dpi=200)
```

`plot_pressure(..., mode='combined')` sums selected pressure distributions;
`mode='separate'` overlays each selected pour's pressure contribution in
independent colors. `pressure_scale` is in **metres/Pa**; `None` automatically
sizes pressure ribbons relative to the section. `show_nodes=True` draws the
sampled points. `plot_resultants(..., scale=...)` instead uses **metres/N**.

Or use the convenience composition:

```python
from concrete_formwork.visualization import plot_section
fig, ax = plot_section(
    sim,
    stage=2,
    pours=['Base', 'Top'],               # concrete regions to show
    show_pressure=True,
    pressure_pours='Top',                # selected pressure contributions
    pressure_mode='combined',
    show_pressure_nodes=True,
    show_resultants=True,
    soil=soil, bracing=braces,
)
```

`plot_pressure_profile(sim, stage=2, pours='Base')` is a separate 1D view of
pressure [kPa] versus elevation [m]. Like the original, Matplotlib remains
optional for numerical-only workflows.

## CSV exports

```python
from concrete_formwork.simulation import (
    export_wall_loads_csv, export_wall_pressures_csv,
)

export_wall_loads_csv(sim, 'wall_resultants.csv')
export_wall_pressures_csv(sim, 'pressure_nodes.csv', pours='Top', samples_per_wall=100)
```

The resultant CSV includes per-wall force vectors and centers of pressure;
the sample CSV includes `wall_index, s_m, x_m, z_m, pressure_Pa`.

## Run examples

```bash
python examples/basic_simulation.py
python examples/complex_profile.py
python examples/composable_layers.py
```

The third example writes `complete_layers.png`, `upper_pour_only.png` and
`pressure_samples.csv` under `examples/output/`.

## Package layout

```text
src/concrete_formwork/
  geometry/
    formwork.py             # Shapely cavity, walls and volume inversion
    supports.py             # SoilRegion and Brace geometry, no solver
  materials/
    concrete.py             # Density/unit weight
  pressure/
    models.py               # Extensible hydrostatic, nonlinear, capped,
                            # tabulated and callable pressure laws
  simulation/
    model.py                # Sequential pours, wall pressure arrays/resultants
    integration.py          # Adaptive quadrature (pressure, moment)
    export.py               # CSV exports
  visualization/
    plot_parameters.py      # Your generic plotting parameters
    plot_basic.py           # Your generic figure utilities
    plot_2d.py              # Your generic 2D primitives + Shapely renderer
    section.py              # Independent engineering drawing layers
examples/
tests/
docs/
```

## License

GPL-3.0-or-later, see [`LICENSE`](LICENSE) and [`CITATION.cff`](CITATION.cff).
