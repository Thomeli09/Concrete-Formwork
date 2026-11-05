"""Lightweight tabular reporting without requiring pandas."""

from __future__ import annotations

import csv
from pathlib import Path

from .model import PouringSimulation, Stage


def wall_load_records(
    simulation: PouringSimulation, *, stage: Stage = None
) -> list[dict[str, int | float | str | None]]:
    """Summarize each physical wall segment in plain Python dictionaries."""
    records: list[dict[str, int | float | str | None]] = []
    for load in simulation.wall_loads(stage):
        center = load.center_of_pressure
        records.append({
            'wall_index': load.wall.index,
            'ring': load.wall.ring,
            'length_m': load.wall.length,
            'normal_x': load.wall.outward_normal[0],
            'normal_z': load.wall.outward_normal[1],
            'force_x_N': load.force[0],
            'force_z_N': load.force[1],
            'force_magnitude_N': load.force_magnitude,
            'center_x_m': center[0] if center else None,
            'center_z_m': center[1] if center else None,
        })
    return records


def export_wall_loads_csv(
    simulation: PouringSimulation, path: str | Path, *, stage: Stage = None
) -> Path:
    """Save integrated loads and centers of pressure for each formwork wall."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = wall_load_records(simulation, stage=stage)
    if not rows:
        raise ValueError('The formwork contains no walls')
    with target.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return target
