"""Composable engineering drawing layers built on generic Matplotlib utilities.

Every low-level drawing function accepts an explicit Axes, adds only its own
layer, and returns artists. No function shows or saves the figure implicitly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from math import isfinite
from typing import Literal

from matplotlib.axes import Axes
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from shapely.geometry import LineString, MultiPolygon, Polygon

from concrete_formwork.geometry import Brace, Formwork, SoilRegion
from concrete_formwork.simulation import PouringSimulation, PourSelection, Stage, WallLoad
from .plot_2d import draw_geometry, draw_reference_line, plot_line, plot_text
from .plot_basic import configure_axes, create_figure
from .plot_parameters import PlotParameters


# Defaults are owned by the concrete visualization layer. Generic drawing
# functions do not know about concrete, formwork or soil.
FORMWORK_STYLE = PlotParameters(color='#292c35', linewidth=2.4)
CONCRETE_STYLE = PlotParameters(alpha=0.65, linewidth=0.6)
PRESSURE_STYLE = PlotParameters(color='#d87338', alpha=0.45, linewidth=1.0)
RESULTANT_STYLE = PlotParameters(color='#b42a25', linewidth=1.8)
SOIL_STYLE = PlotParameters(color='#a49a8c', alpha=0.42, hatch='///', linewidth=0.6)
BRACE_STYLE = PlotParameters(color='#526678', linewidth=2.5, marker='o', markersize=4)


def plot_formwork(
    ax: Axes, formwork: Formwork, *, parameters: PlotParameters | None = None,
    label: str | None = 'Formwork',
) -> list[Line2D]:
    """Draw only physical wall edges; the implicit top is not drawn."""
    style = parameters if parameters is not None else FORMWORK_STYLE
    return [plot_line(ax, [wall.start[0], wall.end[0]], [wall.start[1], wall.end[1]],
                      parameters=style, label=label if i == 0 else None)
            for i, wall in enumerate(formwork.walls)]


def plot_concrete(
    ax: Axes, simulation: PouringSimulation, *, stage: Stage = None,
    pours: PourSelection = None, parameters: PlotParameters | None = None,
) -> list[Artist]:
    """Fill the selected pour(s) using independent Shapely geometries."""
    n = simulation._stage_number(stage)
    selected = simulation._selected_pours(n, pours)
    opts = parameters or CONCRETE_STYLE
    artists: list[Artist] = []
    for pour in selected:
        artists.extend(draw_geometry(
            ax, pour.region, parameters=opts, color=opts.color_at() or pour.concrete.color,
            edgecolor='none', label=f'{pour.name} — {pour.concrete.name}', zorder=2,
        ))
    return artists


def plot_soil(
    ax: Axes, soil: SoilRegion | Polygon | MultiPolygon | Sequence[SoilRegion | Polygon | MultiPolygon],
    *, parameters: PlotParameters | None = None,
) -> list[Artist]:
    """Plot one or several soil regions, without requiring a soil solver."""
    items = [soil] if isinstance(soil, (SoilRegion, Polygon, MultiPolygon)) else list(soil)
    base = parameters or SOIL_STYLE
    artists: list[Artist] = []
    for i, item in enumerate(items):
        if isinstance(item, SoilRegion):
            geometry, name = item.geometry, item.name
            style = replace(base, color=item.color, hatch=item.hatch) if parameters is None else base
        else:
            geometry, name, style = item, f'Soil {i + 1}', base
        artists.extend(draw_geometry(ax, geometry, parameters=style, label=name,
                                     edgecolor=style.color_at(), zorder=0))
    return artists


def plot_bracing(
    ax: Axes, bracing: Brace | LineString | Sequence[Brace | LineString], *,
    parameters: PlotParameters | None = None,
) -> list[Artist]:
    """Draw independently selectable structural brace outlines."""
    braces = [bracing] if isinstance(bracing, (Brace, LineString)) else list(bracing)
    style = parameters or BRACE_STYLE
    artists: list[Artist] = []
    for i, brace in enumerate(braces):
        geometry = brace.geometry if isinstance(brace, Brace) else brace
        color = style.color_at() if parameters is not None else (brace.color if isinstance(brace, Brace) else style.color_at())
        name = brace.name if isinstance(brace, Brace) else f'Brace {i + 1}'
        artists.extend(draw_geometry(ax, geometry, parameters=style,
                                     edgecolor=color, label=name, zorder=6))
    return artists


def _pressure_scale(simulation: PouringSimulation, loads: Sequence[WallLoad],
                    pressure_scale: float | None) -> float:
    if pressure_scale is not None:
        if not isfinite(pressure_scale) or pressure_scale < 0:
            raise ValueError('pressure_scale must be finite and non-negative (metres/Pa)')
        return float(pressure_scale)
    peak = max((v for load in loads for v in load.profile.pressure), default=0.0)
    bounds = simulation.formwork.cavity.bounds
    span = max(bounds[2] - bounds[0], bounds[3] - bounds[1], 1e-3)
    return 0.20 * span / peak if peak > 0 else 0.0


def _pressure_artists(ax: Axes, loads: Sequence[WallLoad], scale: float,
                      style: PlotParameters, *, label: str | None,
                      show_nodes: bool = False) -> list[Artist]:
    """Draw pressure ribbon polygons using real wall-local sample positions."""
    artists: list[Artist] = []
    legend_added = False
    for load in loads:
        wall = load.wall
        nx, nz = wall.outward_normal
        for piece in load.pieces:
            coords = [
                (wall.start[0] + s * (wall.end[0] - wall.start[0]) / wall.length,
                 wall.start[1] + s * (wall.end[1] - wall.start[1]) / wall.length)
                for s in piece.s
            ]
            outer = [(x + scale * p * nx, z + scale * p * nz)
                     for (x, z), p in zip(coords, piece.pressure, strict=True)]
            # This forms a strip between the formwork and the sampled profile.
            # With a zero pressure at a tip the vertices can coincide (valid).
            if scale and any(piece.pressure):
                polygon = Polygon([*coords, *reversed(outer)])
                artists.extend(draw_geometry(ax, polygon, parameters=style,
                                             edgecolor=style.color_at(),
                                             label=label if not legend_added else None,
                                             zorder=3))
                legend_added = True
                if show_nodes:
                    nodes_style = replace(style, linestyle='None', marker='o',
                                          markersize=2.3, alpha=0.85)
                    artists.append(plot_line(ax, [p[0] for p in outer],
                                             [p[1] for p in outer],
                                             parameters=nodes_style))
    return artists


def plot_pressure(
    ax: Axes, simulation: PouringSimulation, *, stage: Stage = None,
    pours: PourSelection = None, mode: Literal['combined', 'separate'] = 'combined',
    pressure_scale: float | None = None,
    samples_per_wall: int = 65,
    nodes_by_wall: Mapping[int, Sequence[float]] | None = None,
    show_nodes: bool = False,
    parameters: PlotParameters | None = None,
) -> list[Artist]:
    """Draw only pressure ribbons; optionally separate each selected pour.

    ``combined`` sums selected pour pressure laws at each wall location.
    ``separate`` draws each selected pour's contribution individually.
    The formwork is not drawn automatically; compose with plot_formwork().
    """
    if mode not in ('combined', 'separate'):
        raise ValueError("mode must be 'combined' or 'separate'")
    n = simulation._stage_number(stage)
    selected = simulation._selected_pours(n, pours)
    opts = parameters or PRESSURE_STYLE
    all_loads = simulation.wall_loads(n, pours=pours, samples_per_wall=samples_per_wall,
                                      nodes_by_wall=nodes_by_wall)
    scale = _pressure_scale(simulation, all_loads, pressure_scale)
    if mode == 'combined':
        return _pressure_artists(ax, all_loads, scale, opts, label='Pressure (combined)',
                                 show_nodes=show_nodes)
    artists: list[Artist] = []
    for i, pour in enumerate(selected):
        # Palette is deterministic and does not modify shared plotting state.
        color = opts.color_at(i) or opts.sample_colormap(len(selected), start=0.15, stop=0.85)[i]
        style = replace(opts, color=color, palette=())
        loads = simulation.wall_loads(n, pours=pour.name,
                    samples_per_wall=samples_per_wall, nodes_by_wall=nodes_by_wall)
        artists.extend(_pressure_artists(ax, loads, scale, style, label=f'Pressure — {pour.name}',
                                         show_nodes=show_nodes))
    return artists


def plot_resultants(
    ax: Axes, simulation: PouringSimulation, *, stage: Stage = None,
    pours: PourSelection = None, scale: float | None = None,
    parameters: PlotParameters | None = None,
) -> list[Artist]:
    """Draw arrows for wall-integrated forces, applied at centers of pressure.

    ``scale`` is [m/N] (arrow length per newton). Automatic uses the largest
    single-wall resultant as ~15% of the maximum section dimension.
    """
    style = parameters or RESULTANT_STYLE
    loads = simulation.wall_loads(stage, pours=pours)
    maximum = max((load.force_magnitude for load in loads), default=0.0)
    bounds = simulation.formwork.cavity.bounds
    span = max(bounds[2] - bounds[0], bounds[3] - bounds[1], 1e-3)
    if scale is None:
        scale = 0.15 * span / maximum if maximum else 0.0
    elif not isfinite(scale) or scale < 0:
        raise ValueError('scale must be finite and non-negative [m/N]')
    artists: list[Artist] = []
    for load in loads:
        point = load.center_of_pressure
        if point is None or not load.force_magnitude:
            continue
        endpoint = (point[0] + scale * load.force[0],
                    point[1] + scale * load.force[1])
        arrow = ax.annotate('', xy=endpoint, xytext=point,
                            arrowprops={'arrowstyle': '-|>', 'lw': style.linewidth,
                                        'color': style.color_at()}, zorder=7)
        artists.append(arrow)
    return artists


def plot_section(
    simulation: PouringSimulation, *,
    stage: Stage = None, ax: Axes | None = None,
    pours: PourSelection = None,
    show_pressure: bool = False, pressure_pours: PourSelection = None,
    pressure_mode: Literal['combined', 'separate'] = 'combined',
    pressure_scale: float | None = None,
    samples_per_wall: int = 65,
    nodes_by_wall: Mapping[int, Sequence[float]] | None = None,
    show_pressure_nodes: bool = False,
    show_resultants: bool = False,
    soil: SoilRegion | Polygon | MultiPolygon | Sequence[SoilRegion | Polygon | MultiPolygon] | None = None,
    bracing: Brace | LineString | Sequence[Brace | LineString] | None = None,
    show_legend: bool = True, title: str | None = None,
    parameters: PlotParameters | None = None,
) -> tuple[Figure, Axes]:
    """Convenience composition of the independent engineering drawing layers."""
    n = simulation._stage_number(stage)
    fig, axis = create_figure(parameters=parameters or PlotParameters(figsize=(9, 6))) if ax is None else (ax.figure, ax)
    if soil is not None:
        plot_soil(axis, soil)
    plot_concrete(axis, simulation, stage=n, pours=pours)
    if show_pressure:
        plot_pressure(axis, simulation, stage=n, pours=pressure_pours, mode=pressure_mode,
                      pressure_scale=pressure_scale, samples_per_wall=samples_per_wall,
                      nodes_by_wall=nodes_by_wall, show_nodes=show_pressure_nodes)
    plot_formwork(axis, simulation.formwork)
    if bracing is not None:
        plot_bracing(axis, bracing)
    if show_resultants:
        plot_resultants(axis, simulation, stage=n, pours=pressure_pours)
    if n:
        level = simulation.level_at(n)
        maximum_x = simulation.formwork.cavity.bounds[2]
        draw_reference_line(axis, level, orientation='horizontal',
                            parameters=PlotParameters(color='#246aa1', linestyle='--', alpha=0.6))
        plot_text(axis, (maximum_x, level), f' z = {level:.3g} m',
                  horizontal_alignment='left', vertical_alignment='bottom',
                  parameters=PlotParameters(color='#246aa1', tick_size=9))
    options = replace(parameters or PlotParameters(),
                      title=title if title is not None else f'Formwork — stage {n}/{len(simulation.pours)}',
                      xlabel='x [m]', ylabel='z [m]', aspect='equal',
                      show_legend=show_legend)
    configure_axes(axis, options)
    axis.margins(0.15)
    return fig, axis


def plot_pressure_profile(
    simulation: PouringSimulation, *, stage: Stage = None,
    pours: PourSelection = None, ax: Axes | None = None, samples: int = 200,
    parameters: PlotParameters | None = None,
) -> tuple[Figure, Axes]:
    """Pressure vs. elevation, independent from the 2D section drawing."""
    if samples < 2:
        raise ValueError('samples must be at least 2')
    fig, axis = create_figure(parameters=parameters or PlotParameters(figsize=(6, 6))) if ax is None else (ax.figure, ax)
    bottom = simulation.formwork.bottom_elevation
    top = simulation.formwork.top_elevation
    elevations = [bottom + i * (top - bottom) / (samples - 1) for i in range(samples)]
    pressures = [simulation.pressure_at(z, stage, pours=pours) / 1000 for z in elevations]
    plot_line(axis, pressures, elevations, parameters=parameters or PlotParameters(color='#b54d28', linewidth=2.0))
    for pour in simulation.pours[:simulation._stage_number(stage)]:
        draw_reference_line(axis, pour.top_elevation, orientation='horizontal',
                            parameters=PlotParameters(color='#888888', linestyle=':', linewidth=1.0))
    configure_axes(axis, replace(parameters or PlotParameters(), title='Pressure versus elevation',
                                 xlabel='Pressure [kPa]', ylabel='z [m]', show_grid=True))
    axis.set_xlim(left=0)
    return fig, axis
