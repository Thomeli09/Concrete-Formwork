"""Former laboratory exercise: concave profile with stepped base and two pours."""

from pathlib import Path

from concrete_formwork import Concrete, Formwork, PouringSimulation
from concrete_formwork.visualization import plot_section


def main() -> None:
    # Previously represented by Node / PLine; now a Shapely cavity.
    profile = [
        (0, 0), (0, -3.65), (-0.7, -3.75), (-0.7, -4.1),
        (0, -4.1), (0, -3.95), (0.35, -3.95), (0.35, -4.1),
        (1.05, -4.1), (1.05, -3.75), (0.35, -3.65), (0.35, 0),
    ]
    simulation = PouringSimulation(Formwork.from_profile(profile, width=2.0))
    simulation.add_pour_to_level('Base', Concrete('C30/37', 23_000, '#a8b9c9'), -2)
    simulation.add_pour_to_level('Upper', Concrete('C35/45', 24_000, '#c9a890'), -0.2)
    result = simulation.summary()
    print(f'Cross-section area: {simulation.formwork.area:.4f} m²')
    print(f'Concrete placed: {result.concrete_volume:.4f} m³')
    print(f'Pressure at lowest point: {result.max_pressure / 1000:.2f} kPa')
    output = Path(__file__).parent / 'output'
    output.mkdir(exist_ok=True)
    fig, _ = plot_section(simulation, show_pressure=True, title='Stepped formwork')
    fig.savefig(output / 'stepped_formwork.png', dpi=160)
    import matplotlib.pyplot as plt
    plt.close(fig)


if __name__ == '__main__':
    main()
