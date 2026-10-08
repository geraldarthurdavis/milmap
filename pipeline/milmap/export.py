"""Static data build consumed by apps/web (see docs/ARCHITECTURE.md §Data contract).

data/build/
  manifest.json                 Manifest (sources, layers, per-day stats, day range)
  days/YYYY-MM-DD.json          DayBundle (areas, lines, diffs, observations for 1 day)
  temporal/<layer>.geojsonl     grid/interval-encoded pieces -> tippecanoe -> tiles/<layer>.pmtiles

Bundles are the v1 path (simple, cacheable, ~100-600 KB gzipped/day). Temporal
PMTiles are the scale path: one archive per layer, instant scrubbing.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import orjson
import shapely
from shapely.geometry.base import BaseGeometry

from .geo.diff import area_km2, control_diff
from .geo.frontline import front_lines
from .geo.temporal import encode_intervals
from .models import (
    DayBundle,
    DayStat,
    Feature,
    FeatureCollection,
    LayerDescriptor,
    Manifest,
    Observation,
    Source,
)
from .timeutil import day_to_date

AREA_SIMPLIFY_DEG = 1e-4  # ~10 m
FRONT_COINCIDENT_DEG = 0.0008  # ~80 m: secondary line "on" the front is dropped
ROUND = 1e-5

# Which area categories bound which line kind (front = union of these).
LINE_FROM = {
    "front": ("assessed_control", "pre_2022"),
    "advance_limit": ("assessed_control", "pre_2022", "assessed_advance"),
    "claimed_limit": ("assessed_control", "pre_2022", "assessed_advance", "claimed_control"),
    "infiltration_limit": ("assessed_control", "pre_2022", "assessed_advance", "assessed_infiltration"),
}


def geojson(g: BaseGeometry) -> dict:
    return orjson.loads(shapely.to_geojson(shapely.set_precision(g, ROUND)))


@dataclass
class BuildInput:
    sources: list[Source]
    # (source_id, category) -> {day: geometry}
    areas: dict[tuple[str, str], dict[int, BaseGeometry]]
    mask: BaseGeometry  # Ukraine adm0 boundary (borders + coast)
    observations: list[Observation] = field(default_factory=list)
    synthetic: bool = False


# Real (non-synthetic) source metadata, keyed by the source_id adapters emit.
# Primary ordering (sources[0] drives the gain/loss histogram) is decided in
# build_input_from_db, not here.
KNOWN_SOURCES: dict[str, Source] = {
    "isw": Source(
        id="isw",
        name="Institute for the Study of War",
        kind="analytic",
        side="unknown",
        reliability="B",
        url="https://understandingwar.org",
        license_note="© ISW & AEI Critical Threats Project — derived control layers; see docs/LICENSING.md",
    ),
    "deepstate": Source(
        id="deepstate",
        name="DeepState",
        kind="osint_map",
        side="UA",
        reliability="B",
        url="https://deepstatemap.live",
        license_note="© DeepState — see docs/LICENSING.md",
    ),
}

# Histogram/primary preference when several control sources are present.
_SOURCE_PRIORITY = ("isw", "deepstate")


def build_input_from_db(con, mask: BaseGeometry, *, synthetic: bool = False) -> BuildInput:
    """Assemble a BuildInput from the DuckDB warehouse (control_snapshot).

    `con` is a db.connect() connection; `mask` is the Ukraine adm0 *boundary*
    (borders + coast) used to clip international edges off the derived fronts.
    """
    from .db import load_control_areas

    areas = load_control_areas(con)
    if not areas:
        raise ValueError("control_snapshot is empty — run `milmap ingest isw-map` first")
    present = {src for (src, _cat) in areas}
    ordered = [s for s in _SOURCE_PRIORITY if s in present] + sorted(
        s for s in present if s not in _SOURCE_PRIORITY
    )
    sources = [
        KNOWN_SOURCES.get(sid)
        or Source(
            id=sid,
            name=sid,
            kind="osint_map",
            side="unknown",
            reliability="F",
            url="",
            license_note="unregistered source",
        )
        for sid in ordered
    ]
    return BuildInput(sources=sources, areas=areas, mask=mask, synthetic=synthetic)


def build(inp: BuildInput, out: Path, *, temporal: bool = False) -> Manifest:
    days_dir = out / "days"
    days_dir.mkdir(parents=True, exist_ok=True)
    all_days = sorted({d for series in inp.areas.values() for d in series})
    if not all_days:
        raise ValueError("no data")
    d0, d1 = all_days[0], all_days[-1]
    obs_by_day: dict[int, list[Observation]] = defaultdict(list)
    for o in inp.observations:
        obs_by_day[o.day].append(o)

    by_source: dict[str, dict[str, dict[int, BaseGeometry]]] = defaultdict(dict)
    for (src, cat), series in inp.areas.items():
        by_source[src][cat] = series

    layer_days: dict[str, list[int]] = defaultdict(list)
    stats: dict[int, DayStat] = {d: DayStat(day=d) for d in range(d0, d1 + 1)}
    line_series: dict[str, list[tuple[int, BaseGeometry]]] = defaultdict(list)
    prev_control: dict[str, BaseGeometry] = {}

    for day in range(d0, d1 + 1):
        layers: dict[str, FeatureCollection] = {}
        for src, cats in by_source.items():
            present = {c: s[day] for c, s in cats.items() if day in s}
            for cat, g in present.items():
                lid = f"{src}.{cat}"
                simp = g.simplify(AREA_SIMPLIFY_DEG, preserve_topology=True)
                layers[lid] = FeatureCollection(
                    features=[
                        Feature(
                            id=lid,
                            geometry=geojson(simp),
                            properties={"source": src, "category": cat, "area_km2": round(area_km2(g), 2)},
                        )
                    ]
                )
                layer_days[lid].append(day)
            front_geom: BaseGeometry | None = None
            for kind, cats_for in LINE_FROM.items():  # "front" first (dict order)
                parts = [present[c] for c in cats_for if c in present]
                if not parts or (kind != "front" and cats_for[-1] not in present):
                    continue
                union = shapely.union_all(parts)
                lines = front_lines(union, inp.mask)
                if kind == "front":
                    front_geom = shapely.MultiLineString(lines) if lines else None
                elif front_geom is not None:
                    # Secondary lines only where they diverge from the front, so the
                    # map shows ISW-style parallel lines instead of overdrawn duplicates.
                    keep = front_geom.buffer(FRONT_COINCIDENT_DEG)
                    lines = [
                        g
                        for ln in lines
                        for g in getattr(ln.difference(keep), "geoms", [ln.difference(keep)])
                        if not g.is_empty and g.geom_type == "LineString" and g.length > 0.003
                    ]
                if not lines:
                    continue
                lid = f"{src}.{kind}"
                layers[lid] = FeatureCollection(
                    features=[
                        Feature(
                            id=f"{lid}.{i}", geometry=geojson(ln), properties={"source": src, "kind": kind}
                        )
                        for i, ln in enumerate(lines)
                    ]
                )
                layer_days[lid].append(day)
                line_series[lid].append((day, shapely.MultiLineString(lines)))
            # day-over-day diff of assessed control (incl. pre-2022)
            ctrl_parts = [present[c] for c in ("assessed_control", "pre_2022") if c in present]
            if ctrl_parts:
                ctrl = shapely.union_all(ctrl_parts)
                if src in prev_control:
                    dd = control_diff(prev_control[src], ctrl)
                    feats = []
                    if not dd.gained.is_empty:
                        feats.append(
                            Feature(
                                id=f"{src}.gain",
                                geometry=geojson(dd.gained),
                                properties={
                                    "source": src,
                                    "change": "ru_gain",
                                    "area_km2": round(dd.gained_km2, 2),
                                },
                            )
                        )
                    if not dd.lost.is_empty:
                        feats.append(
                            Feature(
                                id=f"{src}.loss",
                                geometry=geojson(dd.lost),
                                properties={
                                    "source": src,
                                    "change": "ua_gain",
                                    "area_km2": round(dd.lost_km2, 2),
                                },
                            )
                        )
                    if feats:
                        layers[f"{src}.diff"] = FeatureCollection(features=feats)
                        layer_days[f"{src}.diff"].append(day)
                    if src == inp.sources[0].id:  # primary source drives the histogram
                        stats[day].ru_gain_km2 = round(dd.gained_km2, 2)
                        stats[day].ua_gain_km2 = round(dd.lost_km2, 2)
                prev_control[src] = ctrl

        day_obs = obs_by_day.get(day, [])
        stats[day].observations = len(day_obs)
        stats[day].claims = sum(1 for o in day_obs if o.status == "claimed")
        if not layers and not day_obs:
            continue
        bundle = DayBundle(day=day, date=day_to_date(day).isoformat(), layers=layers, observations=day_obs)
        (days_dir / f"{bundle.date}.json").write_bytes(
            orjson.dumps(bundle.model_dump(mode="json"))
        )

    descriptors = [
        LayerDescriptor(
            id=lid,
            source_id=lid.split(".", 1)[0],
            geom="line" if lid.split(".", 1)[1] in LINE_FROM else "area",
            category=lid.split(".", 1)[1],
            day_ranges=_ranges(days),
        )
        for lid, days in sorted(layer_days.items())
    ]

    if temporal:
        tdir = out / "temporal"
        tdir.mkdir(exist_ok=True)
        for (src, cat), series in inp.areas.items():
            _write_temporal(
                tdir / f"{src}.{cat}.geojsonl", sorted(series.items()), {"source": src, "category": cat}
            )
        for lid, series in line_series.items():
            _write_temporal(tdir / f"{lid}.geojsonl", series, {"layer": lid})

    manifest = Manifest(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        synthetic=inp.synthetic,
        day_min=d0,
        day_max=d1,
        sources=inp.sources,
        layers=descriptors,
        stats=[stats[d] for d in range(d0, d1 + 1)],
    )
    (out / "manifest.json").write_bytes(
        orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    )
    return manifest


def _ranges(days: Iterable[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for d in sorted(days):
        if out and d == out[-1][1] + 1:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def _write_temporal(path: Path, series: list[tuple[int, BaseGeometry]], props: dict) -> None:
    with path.open("wb") as fh:
        for p in encode_intervals(series):
            fh.write(
                orjson.dumps(
                    {
                        "type": "Feature",
                        "geometry": geojson(p.geom),
                        "properties": {**props, "vf": p.vf, "vt": p.vt, "cell": f"{p.cell[0]}:{p.cell[1]}"},
                    }
                )
            )
            fh.write(b"\n")
