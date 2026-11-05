"""Sequential, horizontally layered concrete pours within a Shapely cavity."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isfinite

from shapely.geometry.base import BaseGeometry

from concrete_formwork.geometry import Formwork, Point2D, Wall
from concrete_formwork.materials import Concrete

type Stage = int | str | None


@dataclass(frozen=True, slots=True)
class Pour:
    """An individual placed region, computed by subtracting two filled regions."""

    name: str
    concrete: Concrete
    bottom_elevation: float
    top_elevation: float
    region: BaseGeometry = field(repr=False, compare=False)
    width: float = 1.0

    @property
    def area(self) -> float:
        return self.region.area

    @property
    def volume(self) -> float:
        return self.area * self.width


@dataclass(frozen=True, slots=True)
class PressurePiece:
    """A wetted wall portion over which pressure varies linearly.

    Force is the outward load of this portion for the *full formwork depth*.
    """

    wall_index: int
    start: Point2D
    end: Point2D
    pressure_start: float  # Pa
    pressure_end: float  # Pa
    outward_normal: Point2D
    width: float

    @property
    def length(self) -> float:
        return hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    @property
    def force_magnitude(self) -> float:
        """Integrated pressure over this wall portion [N]."""
        return (self.pressure_start + self.pressure_end) / 2 * self.length * self.width

    @property
    def force(self) -> Point2D:
        return (
            self.outward_normal[0] * self.force_magnitude,
            self.outward_normal[1] * self.force_magnitude,
        )

    @property
    def center_of_pressure(self) -> Point2D:
        """Exact resultant application point for a linear pressure profile."""
        s = self.pressure_start + self.pressure_end
        t = (self.pressure_start + 2 * self.pressure_end) / (3 * s) if s else 0.5
        return (
            self.start[0] + t * (self.end[0] - self.start[0]),
            self.start[1] + t * (self.end[1] - self.start[1]),
        )


@dataclass(frozen=True, slots=True)
class WallLoad:
    """Force and center of pressure aggregated over one physical wall."""

    wall: Wall
    pieces: tuple[PressurePiece, ...]

    @property
    def force(self) -> Point2D:
        return (
            sum(p.force[0] for p in self.pieces),
            sum(p.force[1] for p in self.pieces),
        )

    @property
    def force_magnitude(self) -> float:
        return sum(p.force_magnitude for p in self.pieces)

    @property
    def center_of_pressure(self) -> Point2D | None:
        total = self.force_magnitude
        if total <= 0:
            return None
        return (
            sum(p.center_of_pressure[0] * p.force_magnitude for p in self.pieces) / total,
            sum(p.center_of_pressure[1] * p.force_magnitude for p in self.pieces) / total,
        )


@dataclass(frozen=True, slots=True)
class StageSummary:
    """Computed quantities at a specific completed pouring stage."""

    stage: int
    top_elevation: float
    filled_area: float
    concrete_volume: float
    remaining_volume: float
    max_pressure: float
    total_force: Point2D
    wall_loads: tuple[WallLoad, ...]


class PouringSimulation:
    """Create discrete concrete layers and evaluate hydrostatic formwork loads.

    Each stage represents the state immediately after a pour. The baseline
    model assumes *all pours present at that stage remain fluid and connected*.
    It does not model setting, thixotropy, pouring rate or dynamic forces.
    """

    def __init__(self, formwork: Formwork) -> None:
        if not isinstance(formwork, Formwork):
            raise TypeError('formwork must be a Formwork instance')
        self.formwork = formwork
        self._pours: list[Pour] = []

    @property
    def pours(self) -> tuple[Pour, ...]:
        return tuple(self._pours)

    def add_pour_to_level(self, name: str, concrete: Concrete, elevation: float) -> Pour:
        """Append a pour ending at an absolute ``z`` elevation [m]."""
        if not name.strip():
            raise ValueError('Pour name must not be empty')
        if any(p.name == name for p in self._pours):
            raise ValueError(f'Duplicate pour name: {name}')
        if not isinstance(concrete, Concrete):
            raise TypeError('concrete must be a Concrete instance')
        if not isfinite(elevation):
            raise ValueError('Pour elevation must be finite')
        bottom = self._pours[-1].top_elevation if self._pours else self.formwork.bottom_elevation
        top = self.formwork.top_elevation
        if elevation <= bottom:
            raise ValueError(f'Pour elevation must be above current fill level {bottom:g} m')
        # A cutting plane above the open formwork fills it, without overflow.
        elevation = min(elevation, top)
        previous = self.formwork.filled_region(bottom)
        current = self.formwork.filled_region(elevation)
        region = current.difference(previous)
        if region.area <= 0:
            raise ValueError('This pour would not add concrete volume')
        pour = Pour(name, concrete, bottom, elevation, region, self.formwork.width)
        self._pours.append(pour)
        return pour

    def add_pour_volume(self, name: str, concrete: Concrete, volume: float) -> Pour:
        """Append a pour of the specified *incremental* volume [m³]."""
        if not isfinite(volume) or volume <= 0:
            raise ValueError('Pour volume must be positive and finite')
        previous = self.filled_volume()
        target = previous + volume
        if target > self.formwork.capacity + 1e-10 * max(1.0, self.formwork.capacity):
            raise ValueError('Pour exceeds formwork capacity')
        target = min(target, self.formwork.capacity)
        return self.add_pour_to_level(
            name, concrete, self.formwork.elevation_for_volume(target)
        )

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

    def level_at(self, stage: Stage = None) -> float:
        n = self._stage_number(stage)
        return self._pours[n - 1].top_elevation if n else self.formwork.bottom_elevation

    def filled_region(self, stage: Stage = None) -> BaseGeometry:
        return self.formwork.filled_region(self.level_at(stage))

    def filled_volume(self, stage: Stage = None) -> float:
        return self.filled_region(stage).area * self.formwork.width

    def pressure_at(self, elevation: float, stage: Stage = None) -> float:
        """Hydrostatic gauge pressure [Pa] at section elevation z [m].

        For each concrete layer above z, sum unit_weight × vertical head.
        This is independent of x and applies only to wetted formwork walls.
        Outside the formwork's vertical range, the returned pressure is zero.
        """
        if not isfinite(elevation):
            raise ValueError('Pressure elevation must be finite')
        n = self._stage_number(stage)
        if not n or elevation < self.formwork.bottom_elevation or elevation >= self.level_at(n):
            return 0.0
        return sum(
            p.concrete.unit_weight * max(0.0, p.top_elevation - max(elevation, p.bottom_elevation))
            for p in self._pours[:n]
        )

    def wall_loads(self, stage: Stage = None) -> tuple[WallLoad, ...]:
        """Integrate piecewise-linear pressure exactly on every straight wall."""
        n = self._stage_number(stage)
        limits = [z for p in self._pours[:n] for z in (p.bottom_elevation, p.top_elevation)]
        loads: list[WallLoad] = []
        for wall in self.formwork.walls:
            z0, z1 = wall.start[1], wall.end[1]
            fractions = [0.0, 1.0]
            if z1 != z0:
                fractions.extend(
                    (z - z0) / (z1 - z0)
                    for z in limits if 0 < (z - z0) / (z1 - z0) < 1
                )
            pieces: list[PressurePiece] = []
            ordered = sorted(set(fractions))
            for t0, t1 in zip(ordered, ordered[1:]):
                a = (
                    wall.start[0] + t0 * (wall.end[0] - wall.start[0]),
                    z0 + t0 * (z1 - z0),
                )
                b = (
                    wall.start[0] + t1 * (wall.end[0] - wall.start[0]),
                    z0 + t1 * (z1 - z0),
                )
                pa, pb = self.pressure_at(a[1], n), self.pressure_at(b[1], n)
                if pa > 0 or pb > 0:
                    pieces.append(
                        PressurePiece(wall.index, a, b, pa, pb, wall.outward_normal,
                                      self.formwork.width)
                    )
            loads.append(WallLoad(wall, tuple(pieces)))
        return tuple(loads)

    def summary(self, stage: Stage = None) -> StageSummary:
        n = self._stage_number(stage)
        loads = self.wall_loads(n)
        volume = self.filled_volume(n)
        return StageSummary(
            stage=n,
            top_elevation=self.level_at(n),
            filled_area=volume / self.formwork.width,
            concrete_volume=volume,
            remaining_volume=max(0.0, self.formwork.capacity - volume),
            max_pressure=self.pressure_at(self.formwork.bottom_elevation, n),
            total_force=(sum(w.force[0] for w in loads), sum(w.force[1] for w in loads)),
            wall_loads=loads,
        )
