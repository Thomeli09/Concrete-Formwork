"""Rectangle: two pours, different unit weights, pressure diagram and CSV."""

from pathlib import Path

from concrete_formwork import Concrete, Formwork, PouringSimulation
from concrete_formwork.simulation import export_wall_loads_csv
from concrete_formwork.visualization import plot_pressure_profile, plot_section


def main() -> None:
    output = Path(__file__).parent / 'output'
    output.mkdir(exist_ok=True)

    # The top line connecting the profile endpoints is an open/free surface.
    formwork = Formwork.from_profile(
        [(0, 3), (0, 0), (2, 0), (2, 3)], width=1.5
    )
    simulation = PouringSimulation(formwork)
    simulation.add_pour_to_level('First pour', Concrete('Mix A', 24_000, '#9eb8c9'), 1.2)
    simulation.add_pour_to_level('Second pour', Concrete('Mix B', 23_000, '#c6a783'), 2.6)

    for stage in (1, 2):
        result = simulation.summary(stage)
        print(f'Stage {stage}: volume={result.concrete_volume:.3f} m³, '
              f'max pressure={result.max_pressure / 1000:.2f} kPa, '
              f'force={result.total_force} N')
        fig, _ = plot_section(simulation, stage=stage, show_pressure=True,
                              show_resultants=True)
        fig.savefig(output / f'formwork_stage_{stage}.png', dpi=160)
        import matplotlib.pyplot as plt
        plt.close(fig)

    fig, _ = plot_pressure_profile(simulation)
    fig.savefig(output / 'pressure_profile.png', dpi=160)
    import matplotlib.pyplot as plt
    plt.close(fig)
    export_wall_loads_csv(simulation, output / 'wall_loads.csv')


if __name__ == '__main__':
    main()
