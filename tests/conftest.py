"""Shared geometry fixtures."""

from __future__ import annotations

import pytest

from concrete_formwork import Concrete, Formwork, PouringSimulation


@pytest.fixture
def rectangle() -> Formwork:
    # x: 0..2 m, z: 0..3 m, section width: 1.5 m.
    return Formwork.from_profile([(0, 3), (0, 0), (2, 0), (2, 3)], width=1.5)


@pytest.fixture
def simulation(rectangle: Formwork) -> PouringSimulation:
    sim = PouringSimulation(rectangle)
    sim.add_pour_to_level('lower', Concrete('Heavy', unit_weight=24_000), 1)
    sim.add_pour_to_level('upper', Concrete('Light', unit_weight=20_000), 2.5)
    return sim
