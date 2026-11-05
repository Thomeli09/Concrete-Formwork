"""Cavity construction, intersection, inversion and shape validation."""

import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon

from concrete_formwork import Formwork


def test_rectangle_metrics(rectangle: Formwork) -> None:
    assert rectangle.area == pytest.approx(6.0)
    assert rectangle.capacity == pytest.approx(9.0)
    assert rectangle.wall_length == pytest.approx(8.0)  # exclude free top edge
    assert rectangle.wall_area == pytest.approx(12.0)
    assert rectangle.height == 3
    assert len(rectangle.walls) == 3
    assert rectangle.filled_region(-10).is_empty
    assert rectangle.filled_region(10).equals(rectangle.cavity)
    assert rectangle.volume_at(1) == pytest.approx(3.0)
    assert rectangle.volume_at(3) == pytest.approx(9.0)
    assert rectangle.elevation_for_volume(6) == pytest.approx(2, abs=1e-8)


def test_reverse_profile_has_identical_normals(rectangle: Formwork) -> None:
    back = Formwork.from_profile([(2, 3), (2, 0), (0, 0), (0, 3)], width=1.5)
    assert back.cavity.equals(rectangle.cavity)
    assert sorted(w.outward_normal for w in back.walls) == sorted(
        w.outward_normal for w in rectangle.walls
    )


def test_nonrectangular_staircase() -> None:
    profile = [(0, 3), (0, 0), (1, 0), (1, 1), (3, 1), (3, 3)]
    form = Formwork.from_profile(profile, width=2)
    assert form.area == pytest.approx(7)
    assert form.volume_at(0.5) == pytest.approx(1)
    assert form.volume_at(2) == pytest.approx(8)
    assert form.elevation_for_volume(8) == pytest.approx(2, abs=1e-8)


def test_concave_shape_can_yield_disconnected_slices() -> None:
    # A U-shaped cavity: cross sections below bridge height split in two.
    # Top connection remains part of a *single* valid polygon.
    polygon = Polygon([(0, 0), (1, 0), (1, 2), (3, 2), (3, 0),
                       (4, 0), (4, 3), (0, 3)])
    form = Formwork.from_polygon(polygon)
    assert isinstance(form.filled_region(1), MultiPolygon)
    assert form.filled_region(1).area == pytest.approx(2)
    assert form.filled_region(3).area == pytest.approx(8)


def test_hole_subtracts_volume_and_has_opposite_normal() -> None:
    form = Formwork.from_polygon(Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        holes=[[(1, 1), (1, 2), (2, 2), (2, 1)]]
    ))
    assert form.area == pytest.approx(15)
    assert form.volume_at(1.5) == pytest.approx(5.5)
    assert len([wall for wall in form.walls if wall.ring == 1]) == 4
    # Hole's left boundary loads point into the hole, not outward from it.
    hole_wall = next(wall for wall in form.walls if wall.ring == 1
                     and wall.start[0] == wall.end[0] == 1)
    assert hole_wall.outward_normal == pytest.approx((1, 0))


@pytest.mark.parametrize('points', [
    [(0, 2), (0, 0)],
    [(0, 3), (0, 0), (2, 0), (2, 2)],
    [(0, 3), (0, 0), (2, 0), (0, 3)],
    [(0, 3), (2, 2), (0, 2), (2, 3)],
])
def test_invalid_profile_raises(points: list[tuple[float, float]]) -> None:
    with pytest.raises(ValueError):
        Formwork.from_profile(points)


def test_invalid_width_and_volume(rectangle: Formwork) -> None:
    with pytest.raises(ValueError):
        Formwork.from_polygon(rectangle.cavity, width=0)
    with pytest.raises(ValueError):
        rectangle.elevation_for_volume(rectangle.capacity + 1)
    with pytest.raises(ValueError):
        rectangle.filled_region(float('nan'))


def test_accepts_shapely_linestring() -> None:
    form = Formwork.from_profile(LineString([(0, 2), (0, 0), (1, 0), (1, 2)]))
    assert form.area == pytest.approx(2)
    assert form.wall_length == pytest.approx(5)


def test_reject_3d_polygon() -> None:
    with pytest.raises(ValueError, match='2D'):
        Formwork.from_polygon(Polygon([(0, 0, 0), (1, 0, 0), (1, 1, 0)]))
