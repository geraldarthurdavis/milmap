"""Grid-clipped interval encoding: N daily snapshots -> one temporal tileset.

Problem: a daily control polygon is one huge multipolygon that changes a little
every day, so naive per-day tiles store the whole front ~1,300+ times.

Trick: clip every day's geometry to a fixed lon/lat grid. Cells far from the
fighting produce byte-identical pieces day after day; consecutive identical
pieces collapse into one feature with a validity interval [vf, vt) (vt
exclusive). Only cells the front runs through churn.

The pieces are written as GeoJSON Lines and tiled with tippecanoe into a single
PMTiles archive. The client shows day `d` by filtering `vf <= d < vt` — scrubbing
the slider is then a filter change, not a network fetch.

Rendering notes (see docs/CARTOGRAPHY.md): fills from these pieces must use
`fill-antialias: false` and no outline, or the grid seams show; outlines come
from the separately encoded *line* layers.

Gap policy: days absent from the input series are treated as "unchanged" — a
piece valid on day 10 and next seen on day 12 with the same hash spans [10, 13).
The manifest's day_ranges records which days were actually observed.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

PRECISION_DEG = 1e-5  # ~1 m; snapping makes identical shapes hash identically


@dataclass(frozen=True)
class Piece:
    cell: tuple[int, int]
    vf: int  # first valid day (inclusive)
    vt: int  # end day (exclusive)
    geom: BaseGeometry


def _cells_for(bounds: tuple[float, float, float, float], size: float) -> list[tuple[int, int]]:
    minx, miny, maxx, maxy = bounds
    ix0, iy0 = math.floor(minx / size), math.floor(miny / size)
    ix1, iy1 = math.floor(maxx / size), math.floor(maxy / size)
    return [(ix, iy) for ix in range(ix0, ix1 + 1) for iy in range(iy0, iy1 + 1)]


def _hash(g: BaseGeometry) -> str:
    return hashlib.blake2b(shapely.to_wkb(g, hex=False), digest_size=16).hexdigest()


def clip_to_grid(geom: BaseGeometry, size: float) -> dict[tuple[int, int], BaseGeometry]:
    if geom.is_empty:
        return {}
    cells = _cells_for(geom.bounds, size)
    boxes = np.array([box(ix * size, iy * size, (ix + 1) * size, (iy + 1) * size) for ix, iy in cells])
    clipped = shapely.intersection(geom, boxes)
    clipped = shapely.set_precision(clipped, PRECISION_DEG)
    clipped = shapely.normalize(clipped)
    dim = shapely.get_dimensions(geom)  # 2 = polygonal, 1 = linear
    out = {}
    for cell, g in zip(cells, clipped, strict=True):
        g = _keep_dim(g, dim)
        if g is not None:
            out[cell] = g
    return out


def _keep_dim(g: BaseGeometry, dim: int) -> BaseGeometry | None:
    """Drop lower-dimensional slivers (edges/points on cell borders)."""
    if g.is_empty:
        return None
    if shapely.get_dimensions(g) == dim and g.geom_type != "GeometryCollection":
        return g
    parts = [p for p in getattr(g, "geoms", [g]) if shapely.get_dimensions(p) == dim]
    if not parts:
        return None
    return shapely.normalize(
        shapely.union_all(parts)
        if dim == 2
        else shapely.line_merge(shapely.MultiLineString(parts))
        if len(parts) > 1
        else parts[0]
    )


def encode_intervals(
    series: Iterable[tuple[int, BaseGeometry]], *, cell_deg: float = 0.25
) -> Iterator[Piece]:
    """series: (day, geometry) sorted by day ascending, one geometry per day."""
    open_: dict[tuple[int, int], tuple[str, int, BaseGeometry]] = {}
    last_day: int | None = None
    for day, geom in series:
        if last_day is not None and day <= last_day:
            raise ValueError(f"series must be strictly ascending (got {day} after {last_day})")
        pieces = clip_to_grid(geom, cell_deg)
        hashes = {c: _hash(g) for c, g in pieces.items()}
        # close pieces that changed or vanished
        for cell in list(open_):
            h, vf, g = open_[cell]
            if hashes.get(cell) != h:
                yield Piece(cell, vf, day, g)
                del open_[cell]
        # open new pieces
        for cell, g in pieces.items():
            if cell not in open_:
                open_[cell] = (hashes[cell], day, g)
        last_day = day
    if last_day is not None:
        for cell, (_, vf, g) in open_.items():
            yield Piece(cell, vf, last_day + 1, g)
