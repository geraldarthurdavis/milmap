"""Derive ISW-style front lines from control polygons.

A *front line* is the part of a control area's boundary that faces the enemy:
the polygon boundary MINUS the stretches that run along an international
border or a coastline (those are where the area simply ends, not where it meets
the other side). Rivers inside Ukraine (e.g. the Dnipro) are *kept* — they are
real fronts.

Each output line is oriented so the controlling side lies on its LEFT. The web
app relies on this: front-line "teeth" are drawn with a symbol layer offset to
one side of the line, so orientation decides which side they point to.
"""

from __future__ import annotations

from collections.abc import Iterable

import shapely
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, substring

from . import WGS84

# ~200 m at 48°N; tolerance for "this boundary segment lies on the border/coast"
DEFAULT_MASK_TOL_DEG = 0.002


def geodesic_length_m(line: BaseGeometry) -> float:
    return float(WGS84.geometry_length(line))


def _as_lines(g: BaseGeometry) -> list[LineString]:
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, MultiLineString):
        return list(g.geoms)
    if hasattr(g, "geoms"):
        out: list[LineString] = []
        for part in g.geoms:
            out.extend(_as_lines(part))
        return out
    return []


def orient_left(line: LineString, area: BaseGeometry, probe_deg: float = 0.0015) -> LineString:
    """Return `line` (or its reverse) such that `area` is on its left-hand side.

    Votes over several sample points so a single odd vertex can't flip it.
    """
    n = max(3, min(15, int(len(line.coords) / 4)))
    votes = 0
    for i in range(n):
        f = (i + 0.5) / n
        seg = substring(line, max(0.0, f - 0.01), min(1.0, f + 0.01), normalized=True)
        coords = list(seg.coords)
        if len(coords) < 2:
            continue
        (x0, y0), (x1, y1) = coords[0], coords[-1]
        dx, dy = x1 - x0, y1 - y0
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        mid = seg.interpolate(0.5, normalized=True)
        left = Point(mid.x - dy / norm * probe_deg, mid.y + dx / norm * probe_deg)
        votes += 1 if area.contains(left) else -1
    return line if votes >= 0 else LineString(list(line.coords)[::-1])


def front_lines(
    area: BaseGeometry,
    mask: BaseGeometry,
    *,
    mask_tol_deg: float = DEFAULT_MASK_TOL_DEG,
    min_length_m: float = 500.0,
) -> list[LineString]:
    """Front lines of `area`.

    area: control (multi)polygon, EPSG:4326.
    mask: lines where `area` ends without facing the enemy — international borders
          and coastline. For Ukraine, `ukraine_adm0.boundary` covers both.
    """
    if area.is_empty:
        return []
    area = shapely.make_valid(area)
    boundary = area.boundary
    front = boundary.difference(mask.buffer(mask_tol_deg))
    merged = linemerge(_as_lines(front)) if not front.is_empty else front
    out = []
    for ln in _as_lines(merged):
        if geodesic_length_m(ln) < min_length_m:
            continue
        out.append(orient_left(ln, area))
    return out


def chaikin(line: LineString, iterations: int = 2) -> LineString:
    """Corner-cutting smoother for low-zoom display. Endpoints are preserved."""
    pts = list(line.coords)
    for _ in range(iterations):
        if len(pts) < 3:
            break
        new = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:], strict=True):
            new.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        new.append(pts[-1])
        pts = new
    return LineString(pts)


def nearest_on_lines(pt: Point, lines: Iterable[LineString]) -> Point | None:
    """Closest point on any front line — the anchor for text callouts."""
    best: tuple[float, Point] | None = None
    for ln in lines:
        p = ln.interpolate(ln.project(pt))
        d = pt.distance(p)
        if best is None or d < best[0]:
            best = (d, p)
    return best[1] if best else None
