"""Test the independent plotting API using the non-interactive Agg backend."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest
from shapely.geometry import LineString, Polygon

from concrete_formwork import Brace, SoilRegion
from concrete_formwork.visualization import (
    PlotParameters, configure_axes, create_figure, plot_bracing,
    plot_concrete, plot_formwork, plot_pressure, plot_resultants,
    plot_section, plot_soil, save_figure,
)
from concrete_formwork.visualization.plot_2d import draw_geometry


def test_independent_rendering_of_each_layer(simulation):
    fig, ax = create_figure(parameters=PlotParameters(figsize=(7, 6)))
    assert len(plot_formwork(ax, simulation.formwork)) == 3
    assert len(plot_concrete(ax, simulation, pours='lower')) == 1
    assert len(plot_concrete(ax, simulation, pours='upper')) == 1
    assert len(plot_pressure(ax, simulation, pours='lower', samples_per_wall=10)) > 0
    assert len(plot_pressure(ax, simulation, pours=['lower', 'upper'], mode='separate')) > 0
    assert len(plot_resultants(ax, simulation, pours='upper')) == 3
    assert len(plot_soil(ax, SoilRegion(Polygon([(-2,-1),(4,-1),(4,0),(-2,0)])))) == 1
    assert len(plot_bracing(ax, Brace.between((0, 1), (-1, -1)))) == 1
    configure_axes(ax, PlotParameters(title='Composed drawing', aspect='equal'))
    plt.close(fig)


def test_section_can_add_soil_and_brace_without_mandating_them(simulation, tmp_path):
    fig, ax = plot_section(
        simulation, show_pressure=True, pressure_mode='separate',
        pressure_pours=['lower', 'upper'], show_resultants=True,
        nodes_by_wall={0: [0.33, 0.89]},
        soil=Polygon([(-1,-1),(3,-1),(3,0),(-1,0)]),
        bracing=LineString([(0, 2), (-1, -0.5)]),
    )
    assert ax.figure is fig
    path = save_figure(fig, tmp_path / 'composed.png', dpi=75)
    assert path.stat().st_size > 1000
    plt.close(fig)


def test_generic_shapely_polygon_holes_preserved():
    polygon = Polygon([(0,0),(3,0),(3,3),(0,3)], holes=[[(1,1),(2,1),(2,2),(1,2)]])
    fig, ax = plt.subplots()
    artists = draw_geometry(ax, polygon, parameters=PlotParameters(color='#bada55'))
    path = artists[0].get_path()
    assert sum(code == 1 for code in path.codes) == 2  # two rings
    assert len(draw_geometry(ax, LineString([(0, 0), (1, 1)]))) == 1
    plt.close(fig)


def test_selection_and_style_errors(simulation):
    fig, ax = plt.subplots()
    with pytest.raises(ValueError):
        plot_pressure(ax, simulation, mode='invalid')
    with pytest.raises(ValueError):
        plot_pressure(ax, simulation, pressure_scale=float('nan'))
    with pytest.raises(ValueError):
        plot_resultants(ax, simulation, scale=-1)
    with pytest.raises(ValueError):
        plot_concrete(ax, simulation, stage=1, pours='upper')
    plt.close(fig)


def test_export_pressure_samples(simulation, tmp_path):
    import csv
    from concrete_formwork.simulation import (
        export_wall_pressures_csv, wall_pressure_records,
    )
    rows = wall_pressure_records(simulation, pours='upper', samples_per_wall=3)
    assert len(rows) >= 9  # at least three physical walls × three nodes
    assert {'wall_index', 's_m', 'pressure_Pa', 'x_m', 'z_m'} == set(rows[0])
    assert all(row['pressure_Pa'] >= 0 for row in rows)
    csv_path = export_wall_pressures_csv(simulation, tmp_path / 'nodes.csv',
                                          pours='upper', samples_per_wall=3)
    with csv_path.open(encoding='utf8', newline='') as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == len(rows)
