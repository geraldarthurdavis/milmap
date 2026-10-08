"""DuckDB warehouse (single file, data/milmap.duckdb). Geometry stored as WKB BLOB
so the core needs no extension; `INSTALL spatial; LOAD spatial;` for ad-hoc SQL.

Tables are append-mostly and idempotent on their natural keys, so any stage can
be rerun for a day range.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

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
