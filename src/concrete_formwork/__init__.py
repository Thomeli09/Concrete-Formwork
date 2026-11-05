"""Formwork cross-section filling and hydrostatic pressure simulation.

All computations use SI units and a 2D (x, z) section extruded over a fixed
out-of-plane width. No plotting dependency is imported until requested.
"""

from .geometry import Formwork, Wall
from .materials import Concrete
from .simulation import Pour, PouringSimulation, PressurePiece, StageSummary, WallLoad

__version__ = '0.1.0'
__all__ = [
    'Concrete', 'Formwork', 'Pour', 'PouringSimulation', 'PressurePiece',
    'StageSummary', 'Wall', 'WallLoad',
]
