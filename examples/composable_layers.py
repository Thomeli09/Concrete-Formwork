"""Two pours, nonlinear pressure, soil and bracing, in independent plot layers."""

from pathlib import Path

import matplotlib.pyplot as plt
from shapely.geometry import Polygon

from concrete_formwork import (
    Brace, CappedHydrostaticPressure, Concrete, Formwork,
    PowerLawPressure, PouringSimulation, SoilRegion,
)
from concrete_formwork.simulation import export_wall_pressures_csv
from concrete_formwork.visualization import (
    PlotParameters, configure_axes, create_figure, plot_bracing,
    plot_concrete, plot_formwork, plot_pressure, plot_resultants,
    plot_section, plot_soil, save_figure,
)


def main() -> None:
    destination = Path(__file__).parent / 'output'
    destination.mkdir(exist_ok=True)

    formwork = Formwork.from_profile([(0, 3), (0, 0), (2, 0), (2, 3)], width=1.5)
    sim = PouringSimulation(formwork)
    sim.add_pour_to_level(
        'Lower', Concrete('C30/37', 24_000, '#81b0ce'), 1.2,
        pressure_law=PowerLawPressure(exponent=1.75),
    )
    sim.add_pour_to_level(
        'Upper', Concrete('C35/45', 23_000, '#e6b475'), 2.7,
        pressure_law=CappedHydrostaticPressure(maximum_pressure=20_000),
    )
    soil = SoilRegion(
        Polygon([(-2, -0.5), (4, -0.5), (4, 0), (-2, 0)]),
        name='Soil under slab',
    )
    braces = [Brace.between((0, 2.1), (-1.5, -0.5)),
              Brace.between((2, 2.1), (3.5, -0.5))]

    # One complete ready-made cross-section, each layer individually selectable.
    fig, _ = plot_section(
        sim, soil=soil, bracing=braces, show_pressure=True,
        pressure_mode='combined', show_pressure_nodes=True,
        show_resultants=True, title='Composite formwork section',
    )
    save_figure(fig, destination / 'complete_layers.png', dpi=160)
    plt.close(fig)

    # Manual composition: draw just the upper pour's geometry and pressure,
    # while retaining separate control of the formwork, soil and bracing.
    fig, ax = create_figure(parameters=PlotParameters(figsize=(10, 6)))
    plot_soil(ax, soil)
    plot_concrete(ax, sim, pours='Upper')
    plot_pressure(ax, sim, pours='Upper', show_nodes=True,
                  nodes_by_wall={0: [0.25, 0.5, 1.75, 2.3, 2.8]},
                  parameters=PlotParameters(color='#ac3650', alpha=0.3))
    plot_resultants(ax, sim, pours='Upper')
    plot_formwork(ax, formwork)
    plot_bracing(ax, braces)
    configure_axes(ax, PlotParameters(title='Upper pour only', xlabel='x [m]',
                                      ylabel='z [m]', aspect='equal',
                                      show_grid=True))
    save_figure(fig, destination / 'upper_pour_only.png', dpi=160)
    plt.close(fig)

    # Inspect the actual stored coordinates (s [m], p [Pa]) for one wall.
    left_wall = next(load for load in sim.wall_loads()
                     if load.wall.start[0] == load.wall.end[0] == 0)
    print('Wall index:', left_wall.wall.index)
    print('First five wall-local pressure samples:')
    for s, pressure in list(zip(left_wall.profile.s, left_wall.profile.pressure))[:5]:
        print(f'  s={s:.3f} m, pressure={pressure / 1000:.2f} kPa')
    print('Integrated wall force:', round(left_wall.force_magnitude), 'N')
    print('Center of pressure (x, z):', left_wall.center_of_pressure)

    export_wall_pressures_csv(sim, destination / 'pressure_samples.csv')


if __name__ == '__main__':
    main()
