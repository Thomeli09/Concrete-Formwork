"""Reusable two-dimensional Matplotlib drawing primitives.

Each function accepts an explicit ``matplotlib.axes.Axes`` and returns its
Matplotlib artist(s), allowing callers to update or remove plots later.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PolyCollection, QuadMesh
from matplotlib.container import BarContainer
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Wedge
from matplotlib.text import Text
from numpy.typing import NDArray

from .plot_basic import add_colorbar
from .plot_parameters import AxisValue, ColorValue, PlotParameters


type PlotData = Sequence[int | float | str | date | datetime] | NDArray[Any]
type NumericData = Sequence[int | float] | NDArray[Any]
type Point2D = tuple[AxisValue, AxisValue]


def _options(parameters: PlotParameters | None) -> PlotParameters:
    """Return a user configuration or an independent default configuration."""
    return parameters if parameters is not None else PlotParameters()


def _artist_kwargs(options: PlotParameters, *, label: str | None = None) -> dict[str, Any]:
    """Common style options understood by most Matplotlib artists."""
    return {
        "color": options.color_at(),
        "linestyle": options.linestyle,
        "linewidth": options.linewidth,
        "alpha": options.alpha,
        "label": label,
    }


def plot_text(
    ax: Axes,
    point: Point2D,
    text: str,
    *,
    parameters: PlotParameters | None = None,
    font_family: str = "sans-serif",
    font_style: str = "normal",
    font_weight: str = "normal",
    horizontal_alignment: Literal["left", "center", "right"] = "center",
    vertical_alignment: Literal["top", "center", "bottom", "baseline"] = "center",
    rotation: float | Literal["horizontal", "vertical"] = 0,
    rotation_mode: Literal["default", "anchor"] = "default",
    coordinates: Literal["data", "axes"] = "data",
    background_color: ColorValue | None = None,
) -> Text:
    """Add text at a data coordinate or fraction of the axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    point : tuple
        Text location (x, y).
    text : str
        Text to display.
    parameters : PlotParameters, optional
        Plot style, notably color, opacity and tick-sized text.
    font_family, font_style, font_weight : str
        Matplotlib font settings.
    horizontal_alignment, vertical_alignment : str
        Text alignment.
    rotation : float or str
        Rotation angle or 'horizontal' / 'vertical'.
    rotation_mode : {'default', 'anchor'}
        Behavior when text is rotated.
    coordinates : {'data', 'axes'}
        Coordinate system. 'axes' uses relative values from 0 to 1.
    background_color : Matplotlib color, optional
        Face color of an optional text bounding box.

    Returns
    -------
    matplotlib.text.Text
        Created text artist.
    """
    options = _options(parameters)
    bbox = None if background_color is None else {"facecolor": background_color, "edgecolor": "none"}
    return ax.text(
        *point, text,
        transform=ax.transAxes if coordinates == "axes" else ax.transData,
        color=options.color_at() or "black", alpha=options.alpha,
        fontfamily=font_family, fontstyle=font_style,
        fontweight=font_weight, fontsize=options.tick_size,
        ha=horizontal_alignment, va=vertical_alignment,
        rotation=rotation, rotation_mode=rotation_mode, bbox=bbox,
    )


def plot_line(
    ax: Axes,
    x: PlotData,
    y: NumericData,
    *,
    parameters: PlotParameters | None = None,
    label: str | None = None,
    color: ColorValue | None = None,
) -> Line2D:
    """Draw one 2D line and return its artist.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    x : sequence or numpy.ndarray
        Horizontal coordinates, including numerical or date-like values.
    y : sequence or numpy.ndarray
        Vertical numerical coordinates; must match ``x`` in length.
    parameters : PlotParameters, optional
        Line appearance settings.
    label : str, optional
        Artist label for legends.
    color : Matplotlib color, optional
        Color overriding the plot parameters.

    Returns
    -------
    matplotlib.lines.Line2D
        Drawn line artist, also editable using ``Line2D.set_data``.
    """
    options = _options(parameters)
    artist = ax.plot(
        x, y,
        color=options.color_at() if color is None else color,
        alpha=options.alpha, linestyle=options.linestyle,
        linewidth=options.linewidth, marker=options.marker,
        markersize=options.markersize, label=label,
    )
    return artist[0]


def plot_empty_line(
    ax: Axes, *, parameters: PlotParameters | None = None, label: str | None = None
) -> Line2D:
    """Create an empty, updateable line on an axes."""
    return plot_line(ax, [], [], parameters=parameters, label=label)


def update_line(line: Line2D, x: PlotData, y: NumericData) -> Line2D:
    """Update coordinates on an existing Matplotlib line artist.

    Parameters
    ----------
    line : matplotlib.lines.Line2D
        Line to modify.
    x, y : sequence or numpy.ndarray
        Replacement horizontal and vertical coordinates.

    Returns
    -------
    matplotlib.lines.Line2D
        The same updated line.
    """
    line.set_data(x, y)
    line.axes.relim()
    line.axes.autoscale_view()
    return line


def plot_series(
    ax: Axes,
    x_series: Sequence[PlotData],
    y_series: Sequence[NumericData],
    *,
    parameters: PlotParameters | None = None,
    labels: Sequence[str | None] | None = None,
) -> list[Line2D]:
    """Draw many x/y series with consistent style and indexed palette colors.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    x_series, y_series : sequence of sequences or numpy.ndarray
        One x and one y sequence per line.
    parameters : PlotParameters, optional
        Shared appearance and optional color palette.
    labels : sequence of str or None, optional
        One legend label per series.

    Returns
    -------
    list of matplotlib.lines.Line2D
        One line artist per input series.

    Raises
    ------
    ValueError
        If the number of x, y or label series does not match.
    """
    if len(x_series) != len(y_series):
        raise ValueError("The numbers of x-series and y-series must match.")
    if labels is not None and len(labels) != len(x_series):
        raise ValueError("'labels' must have one entry per series.")
    options = _options(parameters)
    return [
        plot_line(
            ax, x, y, parameters=options,
            label=None if labels is None else labels[index],
            color=options.color_at(index),
        )
        for index, (x, y) in enumerate(zip(x_series, y_series, strict=True))
    ]


def draw_reference_line(
    ax: Axes,
    value: AxisValue | PlotData,
    *,
    parameters: PlotParameters | None = None,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    relative: bool = True,
    secondary_limits: tuple[float, float] = (0.0, 1.0),
    label: str | None = None,
) -> Line2D | LineCollection | list[Line2D]:
    """Draw vertical/horizontal reference lines using relative or data bounds.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    value : scalar or sequence
        Location(s) of the reference line along its primary axis.
    parameters : PlotParameters, optional
        Line appearance.
    orientation : {'vertical', 'horizontal'}, default 'vertical'
        Line direction.
    relative : bool, default True
        Interpret secondary_limits as fractions of the axes if True,
        otherwise as data coordinates.
    secondary_limits : tuple of float, default (0, 1)
        Start/end positions on the secondary axis.
    label : str, optional
        Legend label.

    Returns
    -------
    matplotlib.lines.Line2D, matplotlib.collections.LineCollection or list
        One artist for scalar input; a list of Line2D artists for multiple
        relatively bounded lines, or one LineCollection for data bounds.
    """
    if orientation not in ("vertical", "horizontal"):
        raise ValueError("'orientation' must be 'vertical' or 'horizontal'.")
    options = _options(parameters)
    low, high = secondary_limits
    kwargs = _artist_kwargs(options, label=label)
    multiple = isinstance(value, (list, tuple, np.ndarray))
    if not relative:
        if orientation == "vertical":
            return ax.vlines(value, low, high, colors=options.color_at(),
                             linestyles=options.linestyle, linewidths=options.linewidth,
                             alpha=options.alpha, label=label)
        return ax.hlines(value, low, high, colors=options.color_at(),
                         linestyles=options.linestyle, linewidths=options.linewidth,
                         alpha=options.alpha, label=label)
    if not (0 <= low <= high <= 1):
        raise ValueError("Relative secondary limits must satisfy 0 <= min <= max <= 1.")
    if multiple:
        values = list(value)
        return [
            (ax.axvline(v, ymin=low, ymax=high, **{**kwargs, "label": label if i == 0 else None})
             if orientation == "vertical" else
             ax.axhline(v, xmin=low, xmax=high, **{**kwargs, "label": label if i == 0 else None}))
            for i, v in enumerate(values)
        ]
    if orientation == "vertical":
        return ax.axvline(value, ymin=low, ymax=high, **kwargs)
    return ax.axhline(value, xmin=low, xmax=high, **kwargs)


def draw_infinite_line(
    ax: Axes,
    point: Point2D,
    *,
    second_point: Point2D | None = None,
    slope: float | None = None,
    parameters: PlotParameters | None = None,
    label: str | None = None,
) -> Line2D:
    """Draw an infinite line through two points or a point and slope.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    point : tuple
        Coordinates of the first point.
    second_point : tuple, optional
        Coordinates of a second point; mutually exclusive with ``slope``.
    slope : float, optional
        Slope of the line; mutually exclusive with ``second_point``.
    parameters : PlotParameters, optional
        Line styling.
    label : str, optional
        Legend label.

    Returns
    -------
    matplotlib.lines.Line2D
        Infinite line artist.

    Raises
    ------
    ValueError
        If both or neither of ``second_point`` and ``slope`` are supplied.
    """
    if (second_point is None) == (slope is None):
        raise ValueError("Provide exactly one of 'second_point' or 'slope'.")
    kwargs = _artist_kwargs(_options(parameters), label=label)
    if slope is not None:
        return ax.axline(point, slope=slope, **kwargs)
    return ax.axline(point, second_point, **kwargs)


def draw_span(
    ax: Axes,
    minimum: AxisValue,
    maximum: AxisValue,
    *,
    parameters: PlotParameters | None = None,
    orientation: Literal["vertical", "horizontal"] = "vertical",
    secondary_limits: tuple[float, float] = (0.0, 1.0),
    label: str | None = None,
) -> Patch:
    """Shade an x- or y-oriented interval with optional hatching.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    minimum, maximum : numeric or date-like
        Lower and upper interval bounds on the primary axis.
    parameters : PlotParameters, optional
        Color, opacity, line width and hatch pattern.
    orientation : {'vertical', 'horizontal'}, default 'vertical'
        Primary axis direction.
    secondary_limits : tuple of float, default (0, 1)
        Fractional bounds of the opposite axis.
    label : str, optional
        Legend label.

    Returns
    -------
    matplotlib.patches.Patch
        Span artist.
    """
    options = _options(parameters)
    low, high = secondary_limits
    kwargs = {
        "facecolor": options.color_at() or "0.7", "edgecolor": options.color_at() or "0.7",
        "hatch": options.hatch, "linestyle": options.linestyle,
        "linewidth": options.linewidth, "alpha": options.alpha, "label": label,
    }
    if orientation == "vertical":
        return ax.axvspan(minimum, maximum, ymin=low, ymax=high, **kwargs)
    if orientation == "horizontal":
        return ax.axhspan(minimum, maximum, xmin=low, xmax=high, **kwargs)
    raise ValueError("'orientation' must be 'vertical' or 'horizontal'.")


def fill_area(
    ax: Axes,
    x: PlotData,
    y: NumericData,
    *,
    secondary_y: NumericData | None = None,
    parameters: PlotParameters | None = None,
    label: str | None = None,
    zorder: float | None = None,
) -> PolyCollection | list[Polygon]:
    """Fill a polygon or the region between two curves.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    x, y : sequence or numpy.ndarray
        Polygon coordinates or coordinates of the first curve.
    secondary_y : sequence or numpy.ndarray, optional
        Second curve. If omitted, a closed polygon is filled.
    parameters : PlotParameters, optional
        Fill color, transparency and hatching.
    label : str, optional
        Legend label.
    zorder : float, optional
        Drawing order relative to other artists.

    Returns
    -------
    matplotlib.collections.PolyCollection or list of Polygon
        Matplotlib collection for a filled region, or polygon patches.
    """
    options = _options(parameters)
    kwargs = {
        "color": options.color_at(), "alpha": options.alpha,
        "hatch": options.hatch, "label": label,
    }
    if zorder is not None:
        kwargs["zorder"] = zorder
    kwargs["linewidth"] = options.linewidth
    kwargs["linestyle"] = options.linestyle
    if secondary_y is not None:
        return ax.fill_between(x, y, secondary_y, **kwargs)
    return ax.fill(x, y, **kwargs)


def plot_bars(
    ax: Axes,
    positions: PlotData,
    heights: NumericData,
    *,
    parameters: PlotParameters | None = None,
    width: float | NumericData = 0.8,
    errors: NumericData | NDArray[Any] | float | None = None,
    horizontal: bool = False,
    baseline: float | NumericData = 0.0,
    label: str | None = None,
) -> BarContainer:
    """Draw vertical or horizontal bars with optional error bars.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    positions : sequence or numpy.ndarray
        Bar centers or category labels.
    heights : sequence or numpy.ndarray
        Bar heights (or horizontal lengths).
    parameters : PlotParameters, optional
        Appearance and palette.
    width : float or sequence, default 0.8
        Bar thickness.
    errors : float or array-like, optional
        Symmetric errors of shape (N,), or asymmetric (2, N).
    horizontal : bool, default False
        Draw horizontal bars when True.
    baseline : float or sequence, default 0
        Bottom (or left) origin of bars.
    label : str, optional
        Legend label.

    Returns
    -------
    matplotlib.container.BarContainer
        Bar artists and optional error bars.
    """
    options = _options(parameters)
    facecolors = [options.color_at(i) for i in range(len(heights))] if options.palette else options.color
    kwargs = {
        "color": facecolors, "alpha": options.alpha,
        "hatch": options.hatch, "label": label,
        "linewidth": options.linewidth,
    }
    if horizontal:
        return ax.barh(positions, heights, height=width, left=baseline,
                       xerr=errors, **kwargs)
    return ax.bar(positions, heights, width=width, bottom=baseline,
                  yerr=errors, **kwargs)


def plot_histogram(
    ax: Axes,
    values: NumericData | Sequence[NumericData],
    *,
    parameters: PlotParameters | None = None,
    bins: int | str | NumericData = "auto",
    histogram_type: Literal["bar", "barstacked", "step", "stepfilled"] = "bar",
    density: bool = False,
    stacked: bool = False,
    cumulative: bool = False,
    weights: NumericData | None = None,
    bottom: float | None = None,
    horizontal: bool = False,
    label: str | Sequence[str] | None = None,
) -> tuple[NDArray[Any], NDArray[Any], BarContainer | list[BarContainer] | list[Polygon] | list[list[Polygon]]]:
    """Plot one or more histograms and return Matplotlib histogram results.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    values : numerical sequence, NumPy array or sequence of datasets
        Samples to bin.
    parameters : PlotParameters, optional
        Appearance settings.
    bins : int, str or sequence, default 'auto'
        Number, estimator name, or explicit bin edges.
    histogram_type : {'bar', 'barstacked', 'step', 'stepfilled'}
        Matplotlib histogram presentation.
    density, stacked, cumulative : bool
        Histogram normalization and accumulation modes.
    weights : sequence, optional
        Sample weights.
    bottom : float, optional
        Baseline of histogram bars.
    horizontal : bool, default False
        Draw horizontal bins when True.
    label : str or sequence of str, optional
        Legend label(s).

    Returns
    -------
    tuple
        Counts, bin edges, and created Matplotlib container(s).
    """
    options = _options(parameters)
    return ax.hist(
        values, bins=bins, density=density, stacked=stacked,
        cumulative=cumulative, weights=weights, bottom=bottom,
        histtype=histogram_type,
        orientation="horizontal" if horizontal else "vertical",
        color=list(options.palette) if options.palette else options.color,
        alpha=options.alpha, label=label,
        log=options.xscale == "log" if horizontal else options.yscale == "log",
    )


def plot_histogram2d(
    ax: Axes,
    x: NumericData,
    y: NumericData,
    *,
    parameters: PlotParameters | None = None,
    bins: int | NumericData | Sequence[NumericData] = 10,
    density: bool = False,
    weights: NumericData | None = None,
    minimum_count: float | None = None,
    maximum_count: float | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    colorbar: bool = False,
) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any], QuadMesh]:
    """Plot a two-dimensional histogram, optionally adding a colorbar.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    x, y : numerical sequence or NumPy array
        Observed x and y data.
    parameters : PlotParameters, optional
        Colormap, transparency and colorbar settings.
    bins : int or sequences, default 10
        Shared bin count, bin edges or per-axis bins.
    density : bool, default False
        Normalize histogram area to one.
    weights : sequence, optional
        Observation weights.
    minimum_count, maximum_count : float, optional
        Minimum/maximum per-bin count accepted for rendering.
    vmin, vmax : float, optional
        Color scale boundaries.
    colorbar : bool, default False
        Add a colorbar to this axes using the computed histogram mappable.

    Returns
    -------
    tuple
        Bin counts, x-bin edges, y-bin edges, and QuadMesh mappable.
    """
    options = _options(parameters)
    result = ax.hist2d(
        x, y, bins=bins, density=density, weights=weights,
        cmin=minimum_count, cmax=maximum_count,
        cmap=options.colormap, vmin=vmin, vmax=vmax, alpha=options.alpha,
    )
    if colorbar:
        add_colorbar(result[3], ax=ax, parameters=options)
    return result


def plot_pie(
    ax: Axes,
    values: NumericData,
    *,
    labels: Sequence[str] | None = None,
    parameters: PlotParameters | None = None,
    display: Literal["percent", "absolute", "both", "none"] = "percent",
    percent_precision: int = 1,
    value_precision: int = 0,
    value_unit: str = "",
    radius: float = 1.0,
    start_angle: float = 0.0,
    label_distance: float = 1.15,
    percent_distance: float = 0.6,
    shadow: bool = False,
    explode: NumericData | None = None,
    annotate: bool = False,
) -> tuple[list[Wedge], list[Text], list[Text]]:
    """Create a pie chart with configurable percentage or absolute labels.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    values : numerical sequence
        Non-negative slice sizes.
    labels : sequence of str, optional
        One label per slice.
    parameters : PlotParameters, optional
        Font sizes, palette, opacity and hatch pattern.
    display : {'percent', 'absolute', 'both', 'none'}
        Numeric text displayed inside slices.
    percent_precision, value_precision : int
        Number of decimal places in annotations.
    value_unit : str
        Unit suffix on absolute annotations.
    radius, start_angle, label_distance, percent_distance : float
        Pie geometry and label placement.
    shadow : bool, default False
        Display slice drop shadows.
    explode : numerical sequence, optional
        Relative offset of each slice.
    annotate : bool, default False
        Place exterior callout arrows with labels instead of regular labels.

    Returns
    -------
    tuple of list
        Wedge patches, regular labels, and numeric annotations. The last
        list is empty when ``display='none'``.
    """
    if display not in ("percent", "absolute", "both", "none"):
        raise ValueError("Unsupported 'display' mode.")
    if labels is not None and len(labels) != len(values):
        raise ValueError("'labels' must have one entry per slice.")
    if percent_precision < 0 or value_precision < 0:
        raise ValueError("Annotation precision must be non-negative.")
    options = _options(parameters)
    array = np.asarray(values, dtype=float)
    if (array.size == 0 or not np.isfinite(array).all()
            or (array < 0).any() or array.sum() <= 0):
        raise ValueError("Pie values must be finite, non-negative, and have a positive sum.")
    total = float(array.sum())

    def format_slice(percent: float) -> str:
        absolute = percent / 100 * total
        pct = f"{percent:.{percent_precision}f}%"
        abs_text = f"{absolute:.{value_precision}f}{(' ' + value_unit) if value_unit else ''}"
        if display == "percent":
            return pct
        if display == "absolute":
            return abs_text
        return f"{pct}\n({abs_text})"

    result = ax.pie(
        array, labels=None if annotate else labels,
        autopct=None if display == "none" else format_slice,
        colors=(list(options.palette) if options.palette else
                [options.color] * len(array) if options.color is not None else None),
        radius=radius, startangle=start_angle,
        labeldistance=label_distance, pctdistance=percent_distance,
        shadow=shadow, explode=explode,
        textprops={"fontsize": options.fontsize},
        wedgeprops={"alpha": options.alpha},
    )
    wedges = list(result[0])
    texts = list(result[1])
    numeric_texts = list(result[2]) if display != "none" else []
    if options.hatch is not None:
        for wedge in wedges:
            wedge.set_hatch(options.hatch)
    if annotate and labels is not None:
        for wedge, label in zip(wedges, labels, strict=True):
            angle = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
            x, y = np.cos(angle), np.sin(angle)
            ax.annotate(
                label, xy=(radius * x, radius * y),
                xytext=(1.35 * radius * np.sign(x), 1.25 * radius * y),
                arrowprops={"arrowstyle": "-"},
                ha="left" if x >= 0 else "right",
                va="center", fontsize=options.fontsize,
            )
    # A pie chart has no meaningful numerical x/y axes. Hide its tick marks,
    # tick labels, spines and grid while retaining slice labels and the title.
    # This remains effective if configure_axes() is called afterward. 
    ax.set_axis_off()
    return wedges, texts, numeric_texts


def plot_image(
    ax: Axes,
    matrix: NumericData | Sequence[NumericData],
    *,
    parameters: PlotParameters | None = None,
    interpolation: str = "nearest",
    origin: Literal["upper", "lower"] = "upper",
    annotate: bool = False,
    value_format: str = ".2f",
    norm: Any = None,
    vmin: float | None = None,
    vmax: float | None = None,
    colorbar: bool = False,
) -> AxesImage:
    """Display a two-dimensional numerical matrix as a colored image.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    matrix : nested sequence or numpy.ndarray
        Rectangular, two-dimensional numerical values.
    parameters : PlotParameters, optional
        Colormap, text styles and colorbar label.
    interpolation : str, default 'nearest'
        Matplotlib image interpolation mode.
    origin : {'upper', 'lower'}, default 'upper'
        Index origin at the top or bottom.
    annotate : bool, default False
        Write formatted numeric values in matrix cells.
    value_format : str, default '.2f'
        Python format specification for numeric annotations.
    norm : matplotlib.colors.Normalize or str, optional
        Optional Matplotlib colormap normalization.
    vmin, vmax : float, optional
        Explicit color scale limits, incompatible with a Normalize instance
        specifying its own limits.
    colorbar : bool, default False
        Add a colorbar attached to this image.

    Returns
    -------
    matplotlib.image.AxesImage
        Image mappable, usable with ``add_colorbar``.

    Raises
    ------
    ValueError
        If the input is not a rectangular two-dimensional matrix.
    """
    try:
        array = np.asarray(matrix, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("'matrix' must be a rectangular numeric matrix.") from exc
    if array.ndim != 2:
        raise ValueError("'matrix' must be two-dimensional.")
    options = _options(parameters)
    image = ax.imshow(
        array, cmap=options.colormap, alpha=options.alpha,
        interpolation=interpolation, origin=origin,
        norm=norm, vmin=vmin, vmax=vmax,
    )
    if annotate:
        for (row, column), value in np.ndenumerate(array):
            ax.text(column, row, format(value, value_format),
                    fontsize=options.fontsize, ha="center", va="center")
    if colorbar:
        add_colorbar(image, ax=ax, parameters=options)
    return image


def draw_circle(
    ax: Axes,
    center: tuple[float, float],
    radius: float,
    *,
    points: int = 100,
    parameters: PlotParameters | None = None,
    filled: bool = False,
    equal_aspect: bool = True,
    label: str | None = None,
) -> Polygon:
    """Draw a circle approximated by an adjustable polygon.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    center : tuple of float
        Circle center as (x, y).
    radius : float
        Positive radius, in data coordinates.
    points : int, default 100
        Number of polygon edges; minimum three.
    parameters : PlotParameters, optional
        Edge and fill appearance.
    filled : bool, default False
        Fill the circle when True.
    equal_aspect : bool, default True
        Use equal horizontal and vertical data unit scales for a round circle.
    label : str, optional
        Legend label.

    Returns
    -------
    matplotlib.patches.Polygon
        Polygon patch representing the circle.

    Raises
    ------
    ValueError
        If radius is not positive or points is less than three.
    """
    if radius <= 0 or points < 3:
        raise ValueError("'radius' must be positive and 'points' must be at least 3.")
    options = _options(parameters)
    angles = np.linspace(0.0, 2 * np.pi, points, endpoint=False)
    vertices = np.column_stack((
        center[0] + radius * np.cos(angles),
        center[1] + radius * np.sin(angles),
    ))
    circle = Polygon(
        vertices, closed=True, fill=filled,
        edgecolor=options.color_at() or "black",
        facecolor=(options.color_at() or "black") if filled else "none",
        linestyle=options.linestyle, linewidth=options.linewidth,
        alpha=options.alpha, hatch=options.hatch, label=label,
    )
    ax.add_patch(circle)
    if equal_aspect:
        ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale_view()
    return circle


__all__ = [
    "plot_text", "plot_line", "plot_empty_line", "update_line", "plot_series",
    "draw_reference_line", "draw_infinite_line", "draw_span", "fill_area",
    "plot_bars", "plot_histogram", "plot_histogram2d", "plot_pie",
    "plot_image", "draw_circle",
]


def draw_geometry(
    ax: Axes,
    geometry: Any,
    *,
    parameters: PlotParameters | None = None,
    color: ColorValue | None = None,
    edgecolor: ColorValue | None = None,
    filled: bool = True,
    label: str | None = None,
    zorder: float = 1,
) -> list[Patch | Line2D]:
    """Draw Shapely polygon(s) with correctly hollow interior rings, or lines.

    The generic Matplotlib helper understands standard Shapely Polygon,
    MultiPolygon, LineString, MultiLineString and GeometryCollection objects.
    It has no dependency on formwork, soil, or engineering models. Returns
    artists for downstream customization, including holes drawn transparently.
    """
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import PathPatch
    from shapely.geometry import GeometryCollection, LineString, MultiLineString
    from shapely.geometry import MultiPolygon, Polygon as ShapelyPolygon
    from shapely.geometry.polygon import orient

    opts = _options(parameters)
    face = color if color is not None else opts.color_at()
    edge = edgecolor if edgecolor is not None else face
    artists: list[Patch | Line2D] = []
    labeled = False

    def add_one(item: Any) -> None:
        nonlocal labeled
        if item.is_empty:
            return
        artist_label = label if not labeled else None
        if isinstance(item, ShapelyPolygon):
            polygon = orient(item, sign=1.0)
            vertices: list[tuple[float, float]] = []
            codes: list[int] = []
            for ring in (polygon.exterior, *polygon.interiors):
                xy = [(float(x), float(y)) for x, y in ring.coords]
                vertices.extend(xy)
                codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY])
            patch = PathPatch(
                MplPath(vertices, codes),
                facecolor=face if filled else 'none',
                edgecolor=edge if edge is not None else 'none',
                linewidth=opts.linewidth,
                linestyle=opts.linestyle,
                alpha=opts.alpha,
                hatch=opts.hatch,
                label=artist_label,
                zorder=zorder,
            )
            ax.add_patch(patch)
            artists.append(patch)
            labeled = True
        elif isinstance(item, LineString):
            xy = list(item.coords)
            if not xy:
                return
            line = plot_line(
                ax, [point[0] for point in xy], [point[1] for point in xy],
                parameters=opts, label=artist_label, color=edge,
            )
            line.set_zorder(zorder)
            artists.append(line)
            labeled = True
        elif isinstance(item, (MultiPolygon, MultiLineString, GeometryCollection)):
            for sub_geometry in item.geoms:
                add_one(sub_geometry)
        else:
            raise TypeError(f'Unsupported Shapely geometry: {type(item).__name__}')

    add_one(geometry)
    ax.autoscale_view()
    return artists


__all__.append('draw_geometry')
