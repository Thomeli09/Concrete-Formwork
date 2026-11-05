"""Optional 2D annotations for soil and bracing (not structural solvers)."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, MultiPolygon, Polygon


@dataclass(frozen=True, slots=True)
class SoilRegion:
    """Shapely soil outline used by the visualization layer."""

    geometry: Polygon | MultiPolygon
    name: str = 'Soil'
    color: str = '#a99f91'
    hatch: str | None = '//'

    def __post_init__(self) -> None:
        if self.geometry.is_empty or not self.geometry.is_valid or self.geometry.area <= 0:
            raise ValueError('SoilRegion requires a nonempty valid Shapely polygon')


@dataclass(frozen=True, slots=True)
class Brace:
    """Straight or polyline bracing outline; no structural stiffness assumed."""

    geometry: LineString
    name: str = 'Brace'
    color: str = '#606d7d'

    def __post_init__(self) -> None:
        if self.geometry.is_empty or self.geometry.length <= 0 or not self.geometry.is_simple:
            raise ValueError('Brace needs a nondegenerate simple Shapely LineString')

    @classmethod
    def between(cls, start: tuple[float, float], end: tuple[float, float], *,
                name: str = 'Brace', color: str = '#606d7d') -> Brace:
        return cls(LineString([start, end]), name=name, color=color)
