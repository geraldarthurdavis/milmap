"""Warehouse round-trip + DB-driven export (the M1 glue), fully offline.

Exercises ingest -> control_snapshot -> build_input_from_db -> export.build
without touching the network or committing any real ISW geometry.
"""

from __future__ import annotations

import json

import shapely
from shapely.geometry import box

from milmap.db import connect, load_control_areas, store_snapshot
from milmap.export import build, build_input_from_db
from milmap.timeutil import day_to_date

# A square "Ukraine"; its boundary stands in for borders + coast (the front mask).
UKR = box(0, 0, 10, 10)


def _ingest_two_days(con) -> None:
    # Russia controls an eastern strip that advances west by one unit on day 2.
    store_snapshot(
        con, source_id="isw", category="assessed_control", day=100,
        geom=box(7, 0, 10, 10), area_km2=30.0, meta={"layers": ["svc/33"]},
    )
    store_snapshot(
        con, source_id="isw", category="assessed_control", day=101,
        geom=box(6, 0, 10, 10), area_km2=40.0, meta={"layers": ["svc/33"]},
    )


def test_snapshot_round_trip_is_idempotent(tmp_path):
    con = connect(tmp_path / "wh.duckdb")
    _ingest_two_days(con)
    # Re-store day 100 with new geometry: upsert, not duplicate.
    store_snapshot(
        con, source_id="isw", category="assessed_control", day=100,
        geom=box(8, 0, 10, 10), area_km2=20.0, meta={},
    )
    areas = load_control_areas(con)
    con.close()
    series = areas[("isw", "assessed_control")]
    assert set(series) == {100, 101}
    assert series[100].equals(shapely.box(8, 0, 10, 10)), "day 100 was overwritten, not duplicated"


def test_export_from_warehouse_is_real_not_synthetic(tmp_path):
    con = connect(tmp_path / "wh.duckdb")
    _ingest_two_days(con)
    inp = build_input_from_db(con, UKR.boundary)
    con.close()

    assert inp.synthetic is False
    assert inp.sources[0].id == "isw"  # primary drives the histogram

    out = tmp_path / "build"
    manifest = build(inp, out, temporal=False)

    assert manifest.synthetic is False
    assert (manifest.day_min, manifest.day_max) == (100, 101)
    assert (out / "manifest.json").exists()

    bundle = json.loads((out / "days" / f"{day_to_date(101).isoformat()}.json").read_bytes())
    assert "isw.assessed_control" in bundle["layers"]
    assert "isw.front" in bundle["layers"], "a front line is derived from control"
    # Day 2 RU advance (one unit west over 10 tall) is recorded as a gain.
    stat = next(s for s in manifest.stats if s.day == 101)
    assert stat.ru_gain_km2 > 0


def test_build_input_requires_data(tmp_path):
    con = connect(tmp_path / "empty.duckdb")
    try:
        import pytest

        with pytest.raises(ValueError, match="control_snapshot is empty"):
            build_input_from_db(con, UKR.boundary)
    finally:
        con.close()
