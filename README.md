# Concrete Formwork

[![Python](https://img.shields.io/badge/Python-3.15%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

Shapely-based analysis of **2D formwork sections**, sequential concrete pours,
concrete volume, and hydrostatic pressure on the formwork walls. Includes
Matplotlib figures and per-wall CSV exports.

**Status:** early engineering prototype (version 0.1.0). This is a fresh API,
not a backwards-compatible update of the older `GeometryLib`/`FormworkLib` code.

## Scope and assumptions

- Coordinates are `(x, z)` in metres; **z is vertical and positive upward**.
- A formwork section is represented by a valid Shapely `Polygon`. An open wall
  profile can be automatically closed by a *horizontal, non-physical top edge*.
- The section is extruded through a **constant out-of-plane width** in metres;
  `area × width = concrete volume`. This is **2.5D**, not arbitrary 3D geometry.
- Each pour occupies the cavity below a chosen horizontal free-surface level,
  minus the filled region from all prior pours. Levels above the cavity top
  are clamped to full capacity. This handles concave outlines,
  recesses, and disjoint cross-sections of one connected cavity. Disconnected
  regions are treated as sharing the prescribed filling level, not individually
  simulated for flow or gravity-fed accessibility.
- **Pressure model: purely hydrostatic**. All placed concrete is assumed fresh,
  fluid and hydraulically connected at the calculation stage. Layer-dependent
  unit weight is used, but neither curing, thixotropy, time, pour rate,
  temperature, friction, arching, dynamic effects nor code-based formwork load
  reductions are modelled. For a staged construction load assessment where
  previous pours set, a constitutive/time-dependent model is still required.
- Holes in a Polygon are excluded from concrete volume; their ring boundaries
  are treated as pressure-bearing contact surfaces.
- All outputs use **SI units**. Pressure Pa (displayed as kPa in figures), force
  N, length m, area m² and volume m³. Input `Concrete.unit_weight` is N/m³.

**Engineering safety:** not independently validated against standards or field
measurements. Do not rely on the results for formwork design or safety-critical
calculations without engineering validation and applicable code checks.

## Installation (Python 3.15+)

Python 3.15 is the target; Shapely **2.2.0+** is required because it supplies
Python 3.15 binaries. The numerical model itself only depends on Shapely;
plotting is optional.

```powershell
git clone https://github.com/Thomeli09/concrete-formwork.git
cd concrete-formwork
py -3.15 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[plot]"
```

On Linux/macOS, replace the environment setup with `python3.15 -m venv .venv`
and `source .venv/bin/activate`.

For development:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

`requirements.txt` and `requirements-dev.txt` are editable-install shortcuts.
The authoritative dependency definition is `pyproject.toml`.

## Quick start

```python
from concrete_formwork import Concrete, Formwork, PouringSimulation
from concrete_formwork.visualization import plot_section

# Open top at z=3 m; constant out-of-plane width = 1.5 m.
formwork = Formwork.from_profile(
    [(0, 3), (0, 0), (2, 0), (2, 3)],
    width=1.5,
)

sim = PouringSimulation(formwork)
sim.add_pour_to_level("First", Concrete("Mix A", unit_weight=24_000), 1.2)
sim.add_pour_to_level("Second", Concrete("Mix B", unit_weight=23_000), 2.6)

# Every pour is its own polygon and concrete material.
for pour in sim.pours:
    print(pour.name, pour.region.geom_type, pour.volume, "m³")

# The model can be evaluated after ANY stage (0, 1, 2, or by pour name).
result = sim.summary(stage=2)
print("Total volume:", result.concrete_volume, "m³")
print("Max hydrostatic pressure:", result.max_pressure / 1000, "kPa")
print("Total outward wall force (x, z):", result.total_force, "N")

fig, ax = plot_section(sim, stage=2, show_pressure=True, show_resultants=True)
fig.savefig("formwork.png", dpi=180)
```

### Volume-controlled pour

```python
sim = PouringSimulation(formwork)
sim.add_pour_volume("Batch 1", Concrete("C30/37"), volume=3.0)
sim.add_pour_volume("Batch 2", Concrete("C35/45"), volume=1.5)
print(sim.level_at())  # 1.5 m for this rectangular section
```

### Use an existing Shapely polygon

```python
from shapely.geometry import Polygon

section = Polygon([(0, 0), (2, 0), (2, 3), (0, 3)])
formwork = Formwork.from_polygon(section, width=2)
print(formwork.area, formwork.capacity, formwork.wall_length)
print(formwork.filled_region(1.5))  # Shapely geometry below z=1.5
```

The `from_polygon` form treats every boundary ring as physical wall. The
`from_profile` form *excludes* the implicitly added upper closing edge from
wall calculations and physical wall length.

### Export and advanced plotting

```python
from concrete_formwork.simulation import export_wall_loads_csv, wall_load_records
from concrete_formwork.visualization import plot_pressure_profile

rows = wall_load_records(sim, stage=1)  # list[dict]
export_wall_loads_csv(sim, "loads.csv", stage=1)
fig, ax = plot_pressure_profile(sim)
fig.savefig("pressure_profile.png")
```

The plotted pressure ribbons project **outside** the cavity along each wall's
outward normal; their extent is scaled for visual clarity and is not a
physical displacement. The true forces are from analytical integration of the
piecewise-linear hydrostatic pressure and account for the formwork width.

## Mathematical model

For pour `i` with unit weight `γᵢ` [N/m³], bottom `bᵢ` [m], and top `tᵢ` [m]:

- Filled cavity up to `z`: `C(z) = cavity ∩ {Z ≤ z}`.
- Geometric region of pour `i`: `C(tᵢ) \ C(bᵢ)`.
- Pour volume: `Vᵢ = area(C(tᵢ) \ C(bᵢ)) × width`.
- Hydrostatic pressure at elevation `z` inside the filled vertical range:
  `p(z) = Σ γᵢ × max(0, tᵢ − max(z, bᵢ))` for each pour present at the stage.

Each straight wall is split at **all material interfaces and free surfaces**.
Pressure is linear within each split piece. Integration is exact:

- `F = (p₀ + p₁) / 2 × wall_piece_length × width`.
- Application point measured from endpoint 0 along the piece:
  `s/L = (p₀ + 2p₁) / [3(p₀ + p₁)]` (when `p₀+p₁ > 0`).
- Normal force vector = `F × outward_normal`.

The implementation returns full wall loads and the force-weighted center of
pressure. Closed boundaries may have nonzero net forces; do not interpret a
single summed vector as a structural design check.

## Examples

```bash
python examples/basic_simulation.py
python examples/complex_profile.py
```

Plots and CSV files are placed under `examples/output/` (ignored by Git). The
second example reproduces the stepped formwork outline from the old lab script
with new Shapely-based computations.

## Source structure

```text
src/concrete_formwork/
  __init__.py
  geometry/
    formwork.py       # Shapely polygon, fill clipping, wall normals, volume inversion
  materials/
    concrete.py       # Concrete unit weight
  simulation/
    model.py          # Sequential pours, stages, pressure and exact wall resultant
    export.py         # CSV and simple per-wall records
  visualization/
    section.py        # Formwork, colored pours, pressure ribbons and pressure profile
examples/
  basic_simulation.py
  complex_profile.py
tests/
  test_geometry.py
  test_simulation.py
  test_visualization.py
```

## Development roadmap

Time-dependent concrete rheology, formwork pressure standards, pour-rate
handling, partially cured preceding layers, transient stage load cases,
interconnected cavity topology, finite elements and arbitrary 3D shapes are
**not implemented**. These require separate validated models; they should not
be inferred from the current hydrostatic solver.

## License and citation

GNU General Public License, version 3 or later. See [`LICENSE`](LICENSE) and
[`CITATION.cff`](CITATION.cff).
