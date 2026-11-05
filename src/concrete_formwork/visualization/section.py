"""Matplotlib renderers for the cavity, individual pours, and wall pressure."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Polygon as PolygonPatch
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.geometry.base import BaseGeometry

from concrete_formwork.simulation import PouringSimulation, Stage

if TYPE_CHECKING:
    from concrete_formwork.simulation import PressurePiece


def _polygons(geometry: BaseGeometry) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [] if geometry.is_empty else [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return [p for g in geometry.geoms for p in _polygons(g)]
    return []


def _paint_region(ax: Axes, region: BaseGeometry, color: str, alpha: float) -> None:
    """Render a polygon with its holes transparently (using Shapely difference)."""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch

    for polygon in _polygons(region):
        polygon = orient(polygon, sign=1.0)
        vertices: list[tuple[float, float]] = []
        codes: list[int] = []
        for ring in [polygon.exterior, *polygon.interiors]:
            pts = list(ring.coords)
            vertices.extend((float(x), float(z)) for x, z in pts)
            codes.extend([Path.MOVETO, *([Path.LINETO] * (len(pts) - 2)), Path.CLOSEPOLY])
        path = Path(vertices, codes)
        patch = PathPatch(path, facecolor=color, edgecolor='none', alpha=alpha)
        # Explicit even-odd fill rule is not uniformly available across MPL
        # versions. Oriented polygon rings (external CCW, holes CW) work with
        # the standard nonzero winding fill rule.
        ax.add_patch(patch)


def plot_section(
    simulation: PouringSimulation,
    *,
    stage: Stage = None,
    ax: Axes | None = None,
    show_pressure: bool = False,
    pressure_scale: float | None = None,
    show_resultants: bool = False,
    show_legend: bool = True,
    title: str | None = None,
) -> tuple[Figure, Axes]:
    """Plot the formwork, selected pour layers, and optionally pressure diagrams.

    Pressure is drawn along the OUTWARD formwork normals. ``pressure_scale``
    is metres/Pa; ``None`` scales the longest arrow to ~20% of section size.
    Returns the Figure and Axes without calling ``plt.show()``.
    """
    n = simulation._stage_number(stage)
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 6), layout='constrained')
    else:
        fig = ax.figure
    formwork = simulation.formwork
    legend: list[Patch] = []
    for pour in simulation.pours[:n]:
        _paint_region(ax, pour.region, pour.concrete.color, 0.67)
        legend.append(Patch(facecolor=pour.concrete.color, alpha=0.67,
                            label=f'{pour.name} — {pour.concrete.name} ({pour.volume:.3g} m³)'))
    for wall in formwork.walls:
        ax.plot((wall.start[0], wall.end[0]), (wall.start[1], wall.end[1]),
                color='#262626', linewidth=2.3, zorder=4)

    if n:
        level = simulation.level_at(n)
        minx, _, maxx, _ = formwork.cavity.bounds
        ax.axhline(level, linestyle='--', linewidth=1.0,
                   color='#2065a0', alpha=0.75, zorder=3)
        ax.text(maxx, level, f'  z = {level:.3g} m', color='#2065a0',
                va='bottom', ha='left', fontsize=9)

    if show_pressure:
        loads = simulation.wall_loads(n)
        max_p = max((max(piece.pressure_start, piece.pressure_end)
                     for load in loads for piece in load.pieces), default=0.0)
        minx, minz, maxx, maxz = formwork.cavity.bounds
        span = max(maxx - minx, maxz - minz, 1e-3)
        scale = pressure_scale if pressure_scale is not None else (0.20 * span / max_p
                                                                  if max_p else 0)
        if not isinstance(scale, (float, int)) or not 0 <= scale < float('inf'):
            raise ValueError('pressure_scale must be a finite non-negative number')
        for load in loads:
            for piece in load.pieces:
                _paint_pressure_piece(ax, piece, float(scale))
            if show_resultants and load.center_of_pressure is not None:
                center = load.center_of_pressure
                normal = load.wall.outward_normal
                length = 0.14 * span
                ax.annotate('', xy=(center[0] + normal[0] * length,
                                    center[1] + normal[1] * length),
                            xytext=center, arrowprops={'arrowstyle': '->',
                                                       'color': '#b82f27', 'lw': 1.7},
                            zorder=8)
        legend.append(Patch(facecolor='#e99664', edgecolor='#b54d28', alpha=0.4,
                            label='Hydrostatic pressure (scaled outward)'))

    ax.set_xlabel('x [m]')
    ax.set_ylabel('z [m]')
    ax.set_title(title if title is not None else f'Formwork — stage {n}/{len(simulation.pours)}')
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(alpha=0.22)
    ax.margins(0.15)
    if show_legend and legend:
        ax.legend(handles=legend, loc='best', fontsize='small')
    return fig, ax


def _paint_pressure_piece(ax: Axes, piece: PressurePiece, scale: float) -> None:
    normal = piece.outward_normal
    a, b = piece.start, piece.end
    oa = (a[0] + normal[0] * scale * piece.pressure_start,
          a[1] + normal[1] * scale * piece.pressure_start)
    ob = (b[0] + normal[0] * scale * piece.pressure_end,
          b[1] + normal[1] * scale * piece.pressure_end)
    ax.add_patch(PolygonPatch([a, b, ob, oa], closed=True,
                              facecolor='#e99664', edgecolor='#b54d28',
                              linewidth=0.7, alpha=0.5, zorder=2))


def plot_pressure_profile(
    simulation: PouringSimulation, *, stage: Stage = None, ax: Axes | None = None,
    samples: int = 200,
) -> tuple[Figure, Axes]:
    """Plot pressure [kPa] as a function of vertical elevation [m]."""
    if samples < 2:
        raise ValueError('samples must be at least 2')
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6), layout='constrained')
    else:
        fig = ax.figure
    bottom = simulation.formwork.bottom_elevation
    top = simulation.formwork.top_elevation
    elevations = [bottom + i * (top - bottom) / (samples - 1) for i in range(samples)]
    ax.plot([simulation.pressure_at(z, stage) / 1000 for z in elevations],
            elevations, color='#b54d28', linewidth=2)
    for pour in simulation.pours[:simulation._stage_number(stage)]:
        ax.axhline(pour.top_elevation, color='#888888', linestyle=':', linewidth=1)
    ax.set_xlabel('Hydrostatic pressure [kPa]')
    ax.set_ylabel('z [m]')
    ax.set_title('Pressure versus elevation')
    ax.grid(alpha=0.25)
    ax.set_xlim(left=0)
    return fig, ax
