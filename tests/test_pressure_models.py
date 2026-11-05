"""Analytical regression tests for nonlinear and piecewise pressure models."""

from math import isclose

import pytest

from concrete_formwork import (
    CallablePressure, CappedHydrostaticPressure, Concrete, Formwork,
    HydrostaticPressure, PowerLawPressure, PouringSimulation, TabulatedPressure,
)


def filled_rectangle(law, *, width=1.0):
    formwork = Formwork.from_profile([(0, 2), (0, 0), (1, 0), (1, 2)], width=width)
    sim = PouringSimulation(formwork, pressure_law=law)
    sim.add_pour_to_level('A', Concrete('Test', unit_weight=10_000), 2)
    return sim


def vertical_load(sim, **kwargs):
    return next(load for load in sim.wall_loads(**kwargs)
                if load.wall.start[0] == load.wall.end[0] == 0)


def test_quadratic_load_and_center_match_analytical_solution():
    # p(z) = 5000*(2-z)**2; integral = 40,000/3 N, center z=0.5 m.
    sim = filled_rectangle(PowerLawPressure(exponent=2.0), width=1)
    load = vertical_load(sim, samples_per_wall=2)
    assert load.force_magnitude == pytest.approx(40_000 / 3, rel=1e-8)
    assert load.center_of_pressure[1] == pytest.approx(0.5, abs=1e-8)
    # Rendering only the two ends is a poor quadratic *drawing*, but should
    # not degrade the integrated force and moment.
    assert load.profile.s == pytest.approx((0, 2))
    assert load.profile.pressure == pytest.approx((20_000, 0)) or load.profile.pressure == pytest.approx((0, 20_000))


def test_capped_law_inserts_breakpoint_and_integrates_exactly():
    sim = filled_rectangle(CappedHydrostaticPressure(maximum_pressure=5_000))
    load = vertical_load(sim, samples_per_wall=2)
    assert load.force_magnitude == pytest.approx(8750, rel=1e-10)
    assert len(load.pieces) == 2
    assert any(isclose(z, 1.5, abs_tol=1e-9) for _, z in load.profile.coordinates)
    assert sim.pressure_at(0) == pytest.approx(5_000)
    assert sim.pressure_at(1.75) == pytest.approx(2_500)


def test_tabulated_pressure_has_explicit_internal_knot():
    law = TabulatedPressure(((0, 0), (1, 1000), (2, 0)))
    sim = filled_rectangle(law)
    load = vertical_load(sim, samples_per_wall=2)
    assert load.force_magnitude == pytest.approx(1000)
    assert load.center_of_pressure[1] == pytest.approx(1.0)
    assert any(p == 1000 for p in load.profile.pressure)


def test_custom_callable_with_knots_and_integral():
    law = CallablePressure(lambda d, h, gamma: gamma * d**2 / h, knots=(0.5, 1.5))
    sim = filled_rectangle(law)
    load = vertical_load(sim, samples_per_wall=3)
    assert load.force_magnitude == pytest.approx(40_000/3, rel=1e-8)
    assert load.center_of_pressure[1] == pytest.approx(0.5, abs=1e-8)
    assert 0.5 in load.profile.s and 1.5 in load.profile.s


def test_user_wall_nodes_and_pressure_vector():
    sim = filled_rectangle(HydrostaticPressure())
    left = vertical_load(sim)
    custom_s = (0.13, 0.41, 1.12, 1.87)
    load = vertical_load(sim, samples_per_wall=2,
                         nodes_by_wall={left.wall.index: custom_s})
    assert all(any(abs(point - value) < 1e-12 for point in load.profile.s)
               for value in custom_s)
    assert len(load.profile.s) == len(load.profile.pressure)
    assert load.force_magnitude == pytest.approx(20_000)
    with pytest.raises(ValueError):
        sim.wall_loads(nodes_by_wall={left.wall.index: [2.5]})
    with pytest.raises(ValueError):
        sim.wall_loads(nodes_by_wall={900: [0.1]})


def test_select_multiple_pour_contributions_and_stage():
    formwork = Formwork.from_profile([(0, 2), (0, 0), (1, 0), (1, 2)])
    sim = PouringSimulation(formwork)
    sim.add_pour_to_level('First', Concrete('A', 10_000), 1,
                          pressure_law=PowerLawPressure(2))
    sim.add_pour_to_level('Second', Concrete('B', 20_000), 2,
                          pressure_law=CappedHydrostaticPressure(5_000))
    assert sim.pressure_at(0, pours='First') == pytest.approx(10_000)
    assert sim.pressure_at(0, pours='Second') == pytest.approx(5_000)
    assert sim.pressure_at(0, pours=['First', 'Second']) == pytest.approx(15_000)
    assert sim.pressure_at(0, stage='First') == pytest.approx(10_000)
    assert vertical_load(sim, pours=1).force_magnitude == pytest.approx(10_000 / 3)
    with pytest.raises(ValueError):
        sim.wall_loads(stage=1, pours='Second')
    assert len(sim.wall_loads(stage=0)[0].pieces) == 0


def test_invalid_pressure_law_results_rejected():
    sim = filled_rectangle(CallablePressure(lambda d, h, g: float('nan')))
    with pytest.raises(ValueError, match='invalid pressure'):
        sim.wall_loads()
    with pytest.raises(ValueError):
        PowerLawPressure(-2)
    with pytest.raises(ValueError):
        TabulatedPressure(((1, 0), (2, 3)))
    with pytest.raises(ValueError):
        CappedHydrostaticPressure(0)


def test_wall_local_callable_uses_s_and_is_integrated():
    # Different pressure function for one wall. At the left face p(s)=1000*s^2
    # with s from the top to the bottom, hence F=1000*(2^3)/3 N.
    f = Formwork.from_profile([(0, 2), (0, 0), (1, 0), (1, 2)])
    sim = PouringSimulation(f, wall_pressure_function=lambda wall, s, base:
                            1000*s*s if wall.start[0] == wall.end[0] == 0 else base)
    sim.add_pour_to_level('A', Concrete('C'), 2)
    load = vertical_load(sim, samples_per_wall=2)
    assert load.force_magnitude == pytest.approx(8000 / 3, rel=1e-8)
    assert load.center_of_pressure[1] == pytest.approx(0.5, abs=1e-8)
