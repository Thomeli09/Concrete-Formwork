"""Sequential concrete pouring with extensible pressure laws and wall-local loads.

Coordinate convention: (x,z) in metres; z is vertically upward. Scalar gauge
pressures are nonnegative and act along each wall's outward unit normal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from math import fsum, hypot, isfinite

from shapely.geometry.base import BaseGeometry

from concrete_formwork.geometry import Formwork, Point2D, Wall
from concrete_formwork.materials import Concrete
from concrete_formwork.pressure import HydrostaticPressure, PressureLaw
from .integration import integrate_pressure

type Stage = int | str | None
type PourSelection = int | str | Sequence[int | str] | None
type WallPressureFunction = Callable[[Wall, float, float], float]


@dataclass(frozen=True, slots=True)
class Pour:
    """Concrete placed between two horizontal levels, as a Shapely region."""

    name: str
    concrete: Concrete
    bottom_elevation: float
    top_elevation: float
    region: BaseGeometry = field(repr=False, compare=False)
    width: float = 1.0
    pressure_law: PressureLaw = field(default_factory=HydrostaticPressure, repr=False, compare=False)

    @property
    def area(self) -> float:
        return self.region.area

    @property
    def volume(self) -> float:
        return self.area * self.width


@dataclass(frozen=True, slots=True)
class PressurePiece:
    """Segment between analytical/user nodes, integrated independently.

    ``s`` and ``pressure`` store drawing samples in wall-local metres and Pa.
    Forces and first moments come from quadrature of the underlying model,
    not from straight-line interpolation of these display samples.
    """

    wall_index: int
    start: Point2D
    end: Point2D
    outward_normal: Point2D
    width: float
    s: tuple[float, ...]
    pressure: tuple[float, ...]
    integral_pressure: float  # integral of p(s) ds [N/m]
    first_moment: float  # integral of s p(s) ds [N] (about wall start)

    @property
    def pressure_start(self) -> float:
        return self.pressure[0]

    @property
    def pressure_end(self) -> float:
        return self.pressure[-1]

    @property
    def length(self) -> float:
        return hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    @property
    def force_magnitude(self) -> float:
        return self.width * self.integral_pressure

    @property
    def force(self) -> Point2D:
        return (self.outward_normal[0] * self.force_magnitude,
                self.outward_normal[1] * self.force_magnitude)

    @property
    def center_of_pressure(self) -> Point2D:
        location = self.first_moment / self.integral_pressure if self.integral_pressure else (self.s[0] + self.s[-1]) / 2
        return _point_on_segment(self.start, self.end, (location - self.s[0]) / (self.s[-1] - self.s[0]))


@dataclass(frozen=True, slots=True)
class WallPressureProfile:
    """Wall-local sampled pressure coordinates (s [m], p [Pa])."""

    wall: Wall
    s: tuple[float, ...]
    pressure: tuple[float, ...]

    @property
    def coordinates(self) -> tuple[Point2D, ...]:
        return tuple(_wall_point(self.wall, value) for value in self.s)


@dataclass(frozen=True, slots=True)
class WallLoad:
    """Numerically integrated loading and sampled profile on one wall."""

    wall: Wall
    pieces: tuple[PressurePiece, ...]
    profile: WallPressureProfile

    @property
    def force_magnitude(self) -> float:
        return fsum(piece.force_magnitude for piece in self.pieces)

    @property
    def force(self) -> Point2D:
        return (self.wall.outward_normal[0] * self.force_magnitude,
                self.wall.outward_normal[1] * self.force_magnitude)

    @property
    def center_of_pressure(self) -> Point2D | None:
        integral = fsum(piece.integral_pressure for piece in self.pieces)
        if integral <= 0:
            return None
        moment = fsum(piece.first_moment for piece in self.pieces)
        return _wall_point(self.wall, moment / integral)


@dataclass(frozen=True, slots=True)
class StageSummary:
    """Stage quantities. Maximum pressure is estimated from sampled wall nodes."""

    stage: int
    top_elevation: float
    filled_area: float
    concrete_volume: float
    remaining_volume: float
    max_pressure: float
    total_force: Point2D
    wall_loads: tuple[WallLoad, ...]


def _wall_point(wall: Wall, s: float) -> Point2D:
    return (wall.start[0] + s * (wall.end[0] - wall.start[0]) / wall.length,
            wall.start[1] + s * (wall.end[1] - wall.start[1]) / wall.length)


def _point_on_segment(a: Point2D, b: Point2D, t: float) -> Point2D:
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


class PouringSimulation:
    """2.5D cavity, concrete pours, and additive per-pour pressure profiles.

    Each pressure law describes the contribution of ONE pour, transmitted
    through all wetted surfaces below the pour. Different laws can be assigned
    per pour, with unit-aware parameters. This is NOT a setting/aging solver.
    """

    def __init__(
        self, formwork: Formwork, *, pressure_law: PressureLaw | None = None,
        wall_pressure_function: WallPressureFunction | None = None,
    ) -> None:
        if not isinstance(formwork, Formwork):
            raise TypeError('formwork must be a Formwork instance')
        self.formwork = formwork
        self.default_pressure_law = pressure_law if pressure_law is not None else HydrostaticPressure()
        self.wall_pressure_function = wall_pressure_function
        self._pours: list[Pour] = []

    @property
    def pours(self) -> tuple[Pour, ...]:
        return tuple(self._pours)

    def add_pour_to_level(
        self, name: str, concrete: Concrete, elevation: float, *,
        pressure_law: PressureLaw | None = None,
    ) -> Pour:
        """Append a pour to elevation z [m], optionally overriding its law."""
        if not name.strip():
            raise ValueError('Pour name must not be empty')
        if any(p.name == name for p in self._pours):
            raise ValueError(f'Duplicate pour name: {name}')
        if not isinstance(concrete, Concrete):
            raise TypeError('concrete must be a Concrete instance')
        if not isfinite(elevation):
            raise ValueError('Pour elevation must be finite')
        bottom = self._pours[-1].top_elevation if self._pours else self.formwork.bottom_elevation
        if elevation <= bottom:
            raise ValueError(f'Pour elevation must be above current fill level {bottom:g} m')
        top = min(elevation, self.formwork.top_elevation)
        region = self.formwork.filled_region(top).difference(self.formwork.filled_region(bottom))
        if region.area <= 0:
            raise ValueError('This pour would not add concrete volume')
        pour = Pour(name, concrete, bottom, top, region, self.formwork.width,
                    pressure_law if pressure_law is not None else self.default_pressure_law)
        self._pours.append(pour)
        return pour

    def add_pour_volume(
        self, name: str, concrete: Concrete, volume: float, *,
        pressure_law: PressureLaw | None = None,
    ) -> Pour:
        if not isfinite(volume) or volume <= 0:
            raise ValueError('Pour volume must be positive and finite')
        target = self.filled_volume() + volume
        if target > self.formwork.capacity + 1e-10 * max(1.0, self.formwork.capacity):
            raise ValueError('Pour exceeds formwork capacity')
        return self.add_pour_to_level(name, concrete,
                self.formwork.elevation_for_volume(min(target, self.formwork.capacity)),
                pressure_law=pressure_law)

    def _stage_number(self, stage: Stage = None) -> int:
        if stage is None:
            return len(self._pours)
        if isinstance(stage, bool):
            raise TypeError('stage must be an integer or pour name')
        if isinstance(stage, str):
            for number, pour in enumerate(self._pours, start=1):
                if pour.name == stage:
                    return number
            raise ValueError(f'Unknown pour name: {stage}')
        if not isinstance(stage, int) or not 0 <= stage <= len(self._pours):
            raise ValueError(f'stage must be 0 to {len(self._pours)} or a pour name')
        return stage

    def _selected_pours(self, n: int, pours: PourSelection) -> tuple[Pour, ...]:
        if pours is None:
            return tuple(self._pours[:n])
        selected = (pours,) if isinstance(pours, (int, str)) else tuple(pours)
        indices: set[int] = set()
        for key in selected:
            index = self._stage_number(key)
            if index == 0 or index > n:
                raise ValueError('Selected pour must exist at the requested stage')
            indices.add(index)
        return tuple(self._pours[i - 1] for i in sorted(indices))

    def level_at(self, stage: Stage = None) -> float:
        n = self._stage_number(stage)
        return self._pours[n - 1].top_elevation if n else self.formwork.bottom_elevation

    def filled_region(self, stage: Stage = None) -> BaseGeometry:
        return self.formwork.filled_region(self.level_at(stage))

    def filled_volume(self, stage: Stage = None) -> float:
        return self.filled_region(stage).area * self.formwork.width

    @staticmethod
    def _contribution(pour: Pour, z: float) -> float:
        if z >= pour.top_elevation:
            return 0.0
        height = pour.top_elevation - pour.bottom_elevation
        depth = min(max(0.0, pour.top_elevation - z), height)
        pressure = float(pour.pressure_law.pressure(depth, height=height,
                                                   unit_weight=pour.concrete.unit_weight))
        if not isfinite(pressure) or pressure < 0:
            raise ValueError(f'Pressure law for pour {pour.name!r} returned invalid pressure: {pressure}')
        return pressure

    def pressure_at(
        self, elevation: float, stage: Stage = None, *, pours: PourSelection = None,
    ) -> float:
        """Gauge pressure [Pa] from chosen pour contributions at elevation z."""
        if not isfinite(elevation):
            raise ValueError('Pressure elevation must be finite')
        n = self._stage_number(stage)
        selected = self._selected_pours(n, pours)
        if not selected or elevation < self.formwork.bottom_elevation or elevation >= self.level_at(n):
            return 0.0
        return fsum(self._contribution(p, elevation) for p in selected)

    def wall_loads(
        self, stage: Stage = None, *, pours: PourSelection = None,
        samples_per_wall: int = 33,
        nodes_by_wall: Mapping[int, Sequence[float]] | None = None,
    ) -> tuple[WallLoad, ...]:
        """Produce profiles and accurately integrated loads on each wall.

        ``samples_per_wall`` governs visualization resolution (includes ends).
        ``nodes_by_wall`` adds explicit local distances s [m] on a wall,
        keyed by wall.index. Boundary and constitutive breakpoints are inserted
        automatically. Quadrature refines independently of display sampling.
        """
        if isinstance(samples_per_wall, bool) or not isinstance(samples_per_wall, int) or samples_per_wall < 2:
            raise ValueError('samples_per_wall must be an integer >= 2')
        n = self._stage_number(stage)
        selected = self._selected_pours(n, pours)
        if nodes_by_wall:
            valid_indices = {w.index for w in self.formwork.walls}
            if any(k not in valid_indices for k in nodes_by_wall):
                raise ValueError('Unknown wall index in nodes_by_wall')
        loads: list[WallLoad] = []
        for wall in self.formwork.walls:
            length = wall.length
            z0, z1 = wall.start[1], wall.end[1]
            dz = z1 - z0
            mandatory: set[float] = {0.0, length}
            if dz != 0:
                for pour in selected:
                    height = pour.top_elevation - pour.bottom_elevation
                    elevation_knots = [pour.bottom_elevation, pour.top_elevation]
                    elevation_knots.extend(
                        pour.top_elevation - d for d in pour.pressure_law.break_depths(
                            height=height, unit_weight=pour.concrete.unit_weight)
                    )
                    for z in elevation_knots:
                        s = length * (z - z0) / dz
                        if 0 < s < length:
                            mandatory.add(s)
                # Separate the wetted from the dry part, including for selected
                # pour-only plots where the stage surface is above this pour.
                surface = self.level_at(n)
                s_surface = length * (surface - z0) / dz
                if 0 < s_surface < length:
                    mandatory.add(s_surface)
            if nodes_by_wall and wall.index in nodes_by_wall:
                for raw_s in nodes_by_wall[wall.index]:
                    s = float(raw_s)
                    if not isfinite(s) or not 0 <= s <= length:
                        raise ValueError(f'Wall {wall.index}: s must be in [0, {length:g}] m')
                    mandatory.add(s)

            def p_at(s: float) -> float:
                z = z0 + dz * s / length
                if not selected or z > self.level_at(n) or z < self.formwork.bottom_elevation:
                    return 0.0
                base_pressure = fsum(self._contribution(p, z) for p in selected)
                value = (self.wall_pressure_function(wall, s, base_pressure)
                         if self.wall_pressure_function is not None else base_pressure)
                value = float(value)
                if not isfinite(value) or value < 0:
                    raise ValueError(f'Invalid wall pressure on wall {wall.index} at s={s:g} m')
                return value

            required = sorted(mandatory)
            pieces: list[PressurePiece] = []
            all_samples: set[float] = set(required)
            all_samples.update(length * i / (samples_per_wall - 1) for i in range(samples_per_wall))
            for a, b in zip(required, required[1:]):
                # Sample at user-chosen positions AND at uniform positions,
                # preserving exact knots in the plotted pressure polyline.
                sample_positions = sorted(s for s in all_samples if a <= s <= b)
                if a not in sample_positions:
                    sample_positions.insert(0, a)
                if b not in sample_positions:
                    sample_positions.append(b)
                integral, first_moment = integrate_pressure(p_at, a, b)
                if integral <= 0:
                    continue
                samples = tuple(p_at(s) for s in sample_positions)
                pieces.append(PressurePiece(
                    wall.index, _wall_point(wall, a), _wall_point(wall, b),
                    wall.outward_normal, self.formwork.width, tuple(sample_positions),
                    samples, integral, first_moment,
                ))
            profile_s = tuple(sorted(all_samples))
            profile = WallPressureProfile(wall, profile_s, tuple(p_at(s) for s in profile_s))
            loads.append(WallLoad(wall, tuple(pieces), profile))
        return tuple(loads)

    def summary(self, stage: Stage = None, *, samples_per_wall: int = 33) -> StageSummary:
        n = self._stage_number(stage)
        loads = self.wall_loads(n, samples_per_wall=samples_per_wall)
        volume = self.filled_volume(n)
        return StageSummary(
            stage=n, top_elevation=self.level_at(n),
            filled_area=volume / self.formwork.width, concrete_volume=volume,
            remaining_volume=max(0.0, self.formwork.capacity - volume),
            max_pressure=max((p for load in loads for p in load.profile.pressure), default=0.0),
            total_force=(fsum(w.force[0] for w in loads), fsum(w.force[1] for w in loads)),
            wall_loads=loads,
        )
