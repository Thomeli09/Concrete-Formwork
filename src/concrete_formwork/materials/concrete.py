"""Material properties used by the hydrostatic pressure model."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class Concrete:
    """A concrete mix with unit weight in N/m³ (not mass density in kg/m³)."""

    name: str
    unit_weight: float = 24_000.0
    color: str = '#8a9db2'

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError('Concrete name must not be empty')
        if not isfinite(self.unit_weight) or self.unit_weight <= 0:
            raise ValueError('Concrete unit_weight must be positive and finite (N/m³)')
        if not self.color:
            raise ValueError('Concrete color must not be empty')

    @classmethod
    def from_density(
        cls, name: str, density: float, *, gravity: float = 9.81, color: str = '#8a9db2'
    ) -> Concrete:
        """Construct from a mass density [kg/m³], converting to unit weight [N/m³]."""
        if not isfinite(density) or density <= 0 or not isfinite(gravity) or gravity <= 0:
            raise ValueError('density and gravity must be positive and finite')
        return cls(name=name, unit_weight=density * gravity, color=color)
