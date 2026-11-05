"""Shapely-backed formwork cavity and pressure-bearing boundaries.

All coordinates use the (x, z) cross-section in metres. A constant depth
(width) perpendicular to the section converts areas into concrete volumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isclose, isfinite

from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.validation import explain_validity

type Point2D = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Wall:
    """Straight wall element, with unit normal pointing out of the cavity."""

    index: int
    start: Point2D
    end: Point2D
    outward_normal: Point2D
    ring: int = 0  # 0 = outer boundary; 1+ = hole boundaries

    @property
    def length(self) -> float:
        return hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    @property
    def midpoint(self) -> Point2D:
        return ((self.start[0] + self.end[0]) / 2, (self.start[1] + self.end[1]) / 2)


@dataclass(frozen=True, slots=True)
class Formwork:
    """Connected 2D cavity extruded over ``width`` metres.

    Use :meth:`from_profile` for an open-topped wall path, or
    :meth:`from_polygon` for a full polygon (optionally with holes).
    """

    cavity: Polygon
    width: float = 1.0
    _closing_edge: tuple[Point2D, Point2D] | None = field(
        default=None, repr=False, compare=False
    )
    walls: tuple[Wall, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.cavity, Polygon):
            raise TypeError('cavity must be a Shapely Polygon')
        if self.cavity.has_z:
            raise ValueError('The formwork polygon must have 2D (x, z) coordinates')
        if self.cavity.is_empty or self.cavity.area <= 0:
            raise ValueError('The cavity must have a positive area')
        if not self.cavity.is_valid:
            raise ValueError(f'Invalid formwork polygon: {explain_validity(self.cavity)}')
        if not isfinite(self.width) or self.width <= 0:
            raise ValueError('width must be a positive finite number (metres)')
        for ring in [self.cavity.exterior, *self.cavity.interiors]:
            if any(not all(isfinite(float(v)) for v in point[:2]) for point in ring.coords):
                raise ValueError('Formwork coordinates must be finite')
        # Exterior CCW, holes CW: right-hand normals point out of the filled area.
        shape = orient(self.cavity, sign=1.0)
        object.__setattr__(self, 'cavity', shape)
        walls: list[Wall] = []
        for ring_number, ring in enumerate([shape.exterior, *shape.interiors]):
            coords = list(ring.coords)
            for p0, p1 in zip(coords[:-1], coords[1:], strict=True):
                start, end = (float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))
                if self._closing_edge is not None and _same_edge(
                    (start, end), self._closing_edge
                ):
                    continue
                length = hypot(end[0] - start[0], end[1] - start[1])
                if length <= 0:
                    continue
                normal = ((end[1] - start[1]) / length, (start[0] - end[0]) / length)
                walls.append(Wall(len(walls), start, end, normal, ring_number))
        object.__setattr__(self, 'walls', tuple(walls))

    @classmethod
    def from_profile(
        cls, points: list[Point2D] | tuple[Point2D, ...] | LineString, *, width: float = 1.0
    ) -> Formwork:
        """Close an open wall chain with an *implicit horizontal free surface*.

        First and last points must be distinct, at the same uppermost elevation;
        the connecting upper edge is not counted as a physical formwork wall.
        A clockwise or counter-clockwise profile is accepted.
        """
        coords = list(points.coords) if isinstance(points, LineString) else list(points)
        if len(coords) < 3:
            raise ValueError('A profile needs at least three coordinates')
        if any(len(p) != 2 for p in coords):
            raise ValueError('Use 2D (x, z) coordinates, not 3D coordinates')
        if any(not all(isfinite(float(v)) for v in p) for p in coords):
            raise ValueError('Profile coordinates must be finite')
        coords = [(float(x), float(z)) for x, z in coords]
        first, last = coords[0], coords[-1]
        if first == last:
            raise ValueError('For a closed shape, use Formwork.from_polygon()')
        if not isclose(first[1], last[1], abs_tol=1e-9, rel_tol=0):
            raise ValueError('Open profile endpoints must share a horizontal top elevation')
        if any(z > first[1] + 1e-9 for _, z in coords):
            raise ValueError('Profile endpoints must be at the highest elevation')
        line = LineString(coords)
        if not line.is_simple:
            raise ValueError('Formwork walls may not self-intersect')
        return cls(Polygon(coords), width=width, _closing_edge=(last, first))

    @classmethod
    def from_polygon(cls, polygon: Polygon, *, width: float = 1.0) -> Formwork:
        """Use an existing cavity polygon; all polygon rings are physical walls."""
        return cls(polygon, width=width)

    @property
    def bottom_elevation(self) -> float:
        return self.cavity.bounds[1]

    @property
    def top_elevation(self) -> float:
        return self.cavity.bounds[3]

    @property
    def height(self) -> float:
        return self.top_elevation - self.bottom_elevation

    @property
    def area(self) -> float:
        """Cross-section area [m²]."""
        return self.cavity.area

    @property
    def capacity(self) -> float:
        """Maximum volume [m³]."""
        return self.area * self.width

    @property
    def wall_length(self) -> float:
        """Total physical wall length (section perimeter excluding an implicit top) [m]."""
        return sum(wall.length for wall in self.walls)

    @property
    def wall_area(self) -> float:
        """Total physical wall area, for a constant-depth extrusion [m²]."""
        return self.wall_length * self.width

    def filled_region(self, elevation: float) -> BaseGeometry:
        """Intersect the cavity with the half-plane ``z <= elevation``.

        The result may be a Polygon or MultiPolygon for a concave shape.
        Empty and completely full levels are handled without extrapolation.
        """
        if not isfinite(elevation):
            raise ValueError('elevation must be finite')
        if elevation <= self.bottom_elevation:
            return Polygon()
        if elevation >= self.top_elevation:
            return self.cavity
        minx, minz, maxx, _ = self.cavity.bounds
        margin = max(1.0, maxx - minx)
        return self.cavity.intersection(box(minx - margin, minz - margin, maxx + margin, elevation))

    def volume_at(self, elevation: float) -> float:
        """Filled volume [m³] if the horizontal free surface is at ``elevation``."""
        return self.filled_region(elevation).area * self.width

    def elevation_for_volume(self, volume: float, *, tolerance: float = 1e-9) -> float:
        """Find fill elevation for a target *cumulative* volume [m³]."""
        if not isfinite(volume) or not 0 <= volume <= self.capacity:
            raise ValueError(f'volume must lie between 0 and {self.capacity:g} m³')
        if volume == 0:
            return self.bottom_elevation
        if volume == self.capacity:
            return self.top_elevation
        lo, hi = self.bottom_elevation, self.top_elevation
        for _ in range(85):
            mid = (lo + hi) / 2
            if self.volume_at(mid) < volume:
                lo = mid
            else:
                hi = mid
            if hi - lo <= tolerance * max(1.0, self.height):
                break
        return (lo + hi) / 2


def _same_edge(
    edge_a: tuple[Point2D, Point2D], edge_b: tuple[Point2D, Point2D]
) -> bool:
    def same(a: Point2D, b: Point2D) -> bool:
        return all(isclose(v, w, abs_tol=1e-9, rel_tol=0) for v, w in zip(a, b, strict=True))
    return (same(edge_a[0], edge_b[0]) and same(edge_a[1], edge_b[1])) or (
        same(edge_a[0], edge_b[1]) and same(edge_a[1], edge_b[0])
    )
