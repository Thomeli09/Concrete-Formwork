"""Layer volumes, hydrostatic pressure, forces, moments and stage selection."""

import pytest

from concrete_formwork import Concrete, Formwork, PouringSimulation


def test_two_layer_volumes_and_pressure(simulation: PouringSimulation) -> None:
    lower, upper = simulation.pours
    assert lower.volume == pytest.approx(3.0)
    assert upper.volume == pytest.approx(4.5)
    assert lower.region.intersection(upper.region).area == pytest.approx(0)
    assert simulation.filled_volume() == pytest.approx(7.5)
    assert simulation.summary().remaining_volume == pytest.approx(1.5)
    assert simulation.pressure_at(3) == 0
    assert simulation.pressure_at(2.5) == 0
    assert simulation.pressure_at(2) == pytest.approx(10_000)
    assert simulation.pressure_at(1) == pytest.approx(30_000)
    assert simulation.pressure_at(0) == pytest.approx(54_000)
    assert simulation.pressure_at(-1) == 0
    assert simulation.summary().max_pressure == pytest.approx(54_000)


def test_stage_selection(simulation: PouringSimulation) -> None:
    assert simulation.summary(0).concrete_volume == 0
    assert simulation.summary(0).max_pressure == 0
    assert simulation.summary('lower').concrete_volume == pytest.approx(3)
    assert simulation.pressure_at(0, 1) == pytest.approx(24_000)
    assert simulation.summary('upper').concrete_volume == pytest.approx(7.5)
    assert simulation.level_at() == 2.5
    with pytest.raises(ValueError):
        simulation.summary('no such pour')
    with pytest.raises(ValueError):
        simulation.summary(3)


def test_rectangle_force_and_center_of_pressure(rectangle: Formwork) -> None:
    sim = PouringSimulation(rectangle)
    sim.add_pour_to_level('full', Concrete('C', 24_000), 3)
    loads = sim.wall_loads()
    assert len(loads) == 3
    # Both vertical walls get triangular load: .5*gamma*h^2*width.
    horizontal_loads = [w for w in loads if w.wall.start[0] == w.wall.end[0]]
    assert len(horizontal_loads) == 2
    for load in horizontal_loads:
        assert load.force_magnitude == pytest.approx(24_000 * 3**2 / 2 * 1.5)
        assert load.center_of_pressure is not None
        assert load.center_of_pressure[1] == pytest.approx(1)
    bottom_load = next(w for w in loads if w.wall.start[1] == w.wall.end[1] == 0)
    assert bottom_load.force == pytest.approx((0, -24_000 * 3 * 2 * 1.5))
    result = sim.summary()
    assert result.total_force == pytest.approx((0, -216_000))


def test_different_materials_split_exactly(simulation: PouringSimulation) -> None:
    loads = simulation.wall_loads()
    left = next(w for w in loads if w.wall.start[0] == w.wall.end[0] == 0)
    # Two pieces: 0..1 (p=54 to 30 kPa), 1..2.5 (30 to 0 kPa).
    assert len(left.pieces) == 2
    expected_integral = (54_000 + 30_000) / 2 * 1 + (30_000 + 0) / 2 * 1.5
    assert left.force_magnitude == pytest.approx(expected_integral * 1.5)


def test_add_pour_by_incremental_volume(rectangle: Formwork) -> None:
    sim = PouringSimulation(rectangle)
    mix = Concrete.from_density('C', 2400)
    assert mix.unit_weight == pytest.approx(23544)
    a = sim.add_pour_volume('first', mix, 3)
    b = sim.add_pour_volume('second', mix, 1.5)
    assert a.top_elevation == pytest.approx(1, abs=1e-8)
    assert b.top_elevation == pytest.approx(1.5, abs=1e-8)
    assert sim.filled_volume() == pytest.approx(4.5, abs=1e-8)


def test_bad_pours_are_atomic(rectangle: Formwork) -> None:
    sim = PouringSimulation(rectangle)
    mix = Concrete('C')
    sim.add_pour_to_level('one', mix, 1)
    for name, level in [('one', 2), ('new', -1), ('new', 1)]:
        with pytest.raises(ValueError):
            sim.add_pour_to_level(name, mix, level)
    with pytest.raises(ValueError):
        sim.add_pour_volume('too large', mix, 100)
    assert len(sim.pours) == 1


def test_pressure_resultants_invariant_to_vertex_direction(rectangle: Formwork) -> None:
    reverse = Formwork.from_profile([(2, 3), (2, 0), (0, 0), (0, 3)], width=1.5)
    results = []
    for f in (rectangle, reverse):
        sim = PouringSimulation(f)
        sim.add_pour_to_level('A', Concrete('A'), 2)
        results.append(sim.summary().total_force)
    assert results[0] == pytest.approx(results[1])


def test_pour_above_top_is_clamped_to_full(rectangle: Formwork) -> None:
    sim = PouringSimulation(rectangle)
    pour = sim.add_pour_to_level('overflow plane', Concrete('C'), 99)
    assert pour.top_elevation == pytest.approx(3)
    assert sim.filled_volume() == pytest.approx(9)
    assert sim.filled_region().equals(rectangle.cavity)
