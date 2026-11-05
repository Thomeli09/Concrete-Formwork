"""Simultaneous numerical integration of pressure and its first moment."""

from __future__ import annotations

from collections.abc import Callable


def integrate_pressure(
    pressure: Callable[[float], float], start: float, end: float, *,
    relative_tolerance: float = 1e-9, max_depth: int = 22,
) -> tuple[float, float]:
    """Return (integral p ds, integral s*p ds) over a straight wall.

    Adaptive Simpson integration provides exact results (up to roundoff) for
    linear profiles, and convergent approximations for smooth nonlinear ones.
    Breakpoints should be supplied by the calling wall discretization.
    """
    if end <= start:
        return 0.0, 0.0

    def evaluate(s: float) -> tuple[float, float]:
        p = pressure(s)
        return p, s * p

    def simpson(a: float, b: float, fa: tuple[float, float],
                fm: tuple[float, float], fb: tuple[float, float]) -> tuple[float, float]:
        return tuple((b - a) / 6 * (v0 + 4 * vm + v1)
                     for v0, vm, v1 in zip(fa, fm, fb, strict=True))  # type: ignore[return-value]

    def refine(a: float, b: float, fa: tuple[float, float], fm: tuple[float, float],
               fb: tuple[float, float], whole: tuple[float, float],
               depth: int) -> tuple[float, float]:
        m = (a + b) / 2
        fl, fr = evaluate((a + m) / 2), evaluate((m + b) / 2)
        left = simpson(a, m, fa, fl, fm)
        right = simpson(m, b, fm, fr, fb)
        refined = (left[0] + right[0], left[1] + right[1])
        if depth == 0 or all(
            abs(refined[k] - whole[k]) <= 15 * relative_tolerance * max(1.0, abs(refined[k]))
            for k in (0, 1)
        ):
            return tuple(refined[k] + (refined[k] - whole[k]) / 15 for k in (0, 1))  # type: ignore[return-value]
        a0, a1 = refine(a, m, fa, fl, fm, left, depth - 1)
        b0, b1 = refine(m, b, fm, fr, fb, right, depth - 1)
        return a0 + b0, a1 + b1

    fa, fb = evaluate(start), evaluate(end)
    middle = evaluate((start + end) / 2)
    return refine(start, end, fa, middle, fb, simpson(start, end, fa, middle, fb), max_depth)
