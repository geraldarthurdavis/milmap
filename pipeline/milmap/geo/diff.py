"""Day-over-day change in control: what was gained, what was lost, how many km²."""

from __future__ import annotations

from dataclasses import dataclass

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from . import WGS84

# Morphological opening radius (~25 m) — removes slivers created when an analyst
# redraws an unchanged stretch of the line slightly differently.
SLIVER_OPEN_DEG = 0.00025
MIN_PART_KM2 = 0.02


def area_km2(g: BaseGeometry) -> float:
    if g.is_empty:
        return 0.0
    a, _ = WGS84.geometry_area_perimeter(g)
    return abs(a) / 1e6


def _clean(g: BaseGeometry) -> BaseGeometry:
    if g.is_empty:
        return g
    opened = g.buffer(-SLIVER_OPEN_DEG).buffer(SLIVER_OPEN_DEG)
    parts = [p for p in getattr(opened, "geoms", [opened]) if isinstance(p, Polygon)]
    parts = [p for p in parts if area_km2(p) >= MIN_PART_KM2]
    return MultiPolygon(parts) if parts else MultiPolygon()


@dataclass
class ControlDiff:
    gained: BaseGeometry  # newly inside `curr`
    lost: BaseGeometry  # inside `prev`, no longer inside `curr`
    gained_km2: float
    lost_km2: float


def control_diff(prev: BaseGeometry, curr: BaseGeometry) -> ControlDiff:
    prev = shapely.make_valid(prev)
    curr = shapely.make_valid(curr)
    gained = _clean(curr.difference(prev))
    lost = _clean(prev.difference(curr))
    return ControlDiff(gained, lost, area_km2(gained), area_km2(lost))
