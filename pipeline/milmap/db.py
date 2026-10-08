"""DuckDB warehouse (single file, data/milmap.duckdb). Geometry stored as WKB BLOB
so the core needs no extension; `INSTALL spatial; LOAD spatial;` for ad-hoc SQL.

Tables are append-mostly and idempotent on their natural keys, so any stage can
be rerun for a day range.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import duckdb
import shapely
from shapely.geometry.base import BaseGeometry

DB_PATH = Path(os.environ.get("MILMAP_DB", "data/milmap.duckdb"))

DDL = """
CREATE TABLE IF NOT EXISTS control_snapshot (
  source_id TEXT, category TEXT, day INTEGER,
  geom_wkb BLOB, area_km2 DOUBLE, meta JSON, ingested_at TIMESTAMP DEFAULT now(),
  PRIMARY KEY (source_id, category, day)
);
CREATE TABLE IF NOT EXISTS front_line (
  source_id TEXT, kind TEXT, day INTEGER, geom_wkb BLOB, length_km DOUBLE,
  PRIMARY KEY (source_id, kind, day)
);
CREATE TABLE IF NOT EXISTS document (
  id TEXT PRIMARY KEY, source_id TEXT, url TEXT, day INTEGER,
  published_at TIMESTAMP, title TEXT, language TEXT, body JSON, footnotes JSON
);
CREATE TABLE IF NOT EXISTS extraction_cache (
  key TEXT PRIMARY KEY, model TEXT, prompt_version TEXT, result JSON, created_at TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS observation (
  id TEXT PRIMARY KEY, day INTEGER, source_id TEXT, document_id TEXT, payload JSON
);
CREATE TABLE IF NOT EXISTS tg_cursor (handle TEXT PRIMARY KEY, last_id BIGINT);
"""


def connect(path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(DDL)
    return con


# ---------------------------------------------------------------- control_snapshot I/O


def store_snapshot(
    con: duckdb.DuckDBPyConnection,
    *,
    source_id: str,
    category: str,
    day: int,
    geom: BaseGeometry,
    area_km2: float,
    meta: dict | None = None,
) -> None:
    """Upsert one area layer for one day. Idempotent on (source_id, category, day),
    so any day range can be re-ingested without duplicating rows."""
    con.execute(
        "INSERT OR REPLACE INTO control_snapshot "
        "(source_id, category, day, geom_wkb, area_km2, meta) "
        "VALUES (?, ?, ?, ?, ?, CAST(? AS JSON))",
        [source_id, category, int(day), shapely.to_wkb(geom), float(area_km2), json.dumps(meta or {})],
    )


def load_control_areas(
    con: duckdb.DuckDBPyConnection,
) -> dict[tuple[str, str], dict[int, BaseGeometry]]:
    """Read the warehouse back into the shape export.BuildInput expects:
    (source_id, category) -> {day: geometry}."""
    rows = con.execute(
        "SELECT source_id, category, day, geom_wkb FROM control_snapshot "
        "ORDER BY source_id, category, day"
    ).fetchall()
    areas: dict[tuple[str, str], dict[int, BaseGeometry]] = defaultdict(dict)
    for src, cat, day, wkb in rows:
        areas[(src, cat)][int(day)] = shapely.from_wkb(bytes(wkb))
    return dict(areas)
