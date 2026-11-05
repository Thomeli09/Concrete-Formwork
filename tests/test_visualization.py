"""Headless rendering and CSV outputs."""

import csv
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pytest

from concrete_formwork import PouringSimulation
from concrete_formwork.simulation import export_wall_loads_csv, wall_load_records
from concrete_formwork.visualization import plot_pressure_profile, plot_section

matplotlib.use('Agg')


def test_export_loads(tmp_path: Path, simulation: PouringSimulation) -> None:
    assert len(wall_load_records(simulation)) == 3
    path = export_wall_loads_csv(simulation, tmp_path / 'subdir' / 'forces.csv')
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert {'force_x_N', 'force_z_N', 'center_z_m'}.issubset(rows[0])


def test_plot_and_save(tmp_path: Path, simulation: PouringSimulation) -> None:
    fig, _ = plot_section(simulation, stage='lower', show_pressure=True,
                             show_resultants=True)
    fig.savefig(tmp_path / 'section.png')
    plt.close(fig)
    fig, _ = plot_pressure_profile(simulation, samples=35)
    fig.savefig(tmp_path / 'profile.png')
    plt.close(fig)
    assert (tmp_path / 'section.png').stat().st_size > 1000
    assert (tmp_path / 'profile.png').stat().st_size > 1000


def test_plot_on_supplied_axes(simulation: PouringSimulation) -> None:
    fig, ax = plt.subplots()
    fig2, ax2 = plot_section(simulation, ax=ax, show_pressure=True)
    assert fig2 is fig and ax2 is ax
    plt.close(fig)


def test_plot_invalid_scale(simulation: PouringSimulation) -> None:
    with pytest.raises(ValueError):
        fig, ax = plot_section(simulation, show_pressure=True, pressure_scale=-1)
