"""milmap CLI. Stages are independent and idempotent per day range:

  milmap isw-discover                  list ISW ArcGIS layers + classification
  milmap ingest isw-map  --from D --to D
  milmap ingest deepstate --from D --to D
  milmap ingest isw-text --from D --to D
  milmap ingest telegram
  milmap extract --from D --to D [--batch]
  milmap fuse    --from D --to D
  milmap export  --out data/build [--temporal]
  milmap tiles   --in data/build/temporal --out data/build/tiles   (needs tippecanoe)
  milmap schema  --out ../packages/schema/schema
  milmap daily                          ingest(all) -> extract -> fuse -> export for [today-3, today]

Dates accept YYYY-MM-DD or day index. Implemented here: isw-discover, schema,
ingest isw-map, export. The rest are wired in PROMPT.md's build plan.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import orjson
import typer

from .models import EXPORT_MODELS
from .timeutil import day_index, day_to_date

# Repo root (milmap/ -> pipeline/ -> repo). Anchor all I/O here so outputs land in
# the repo-root data/ dir — matching .gitignore and the Vite dev server's DATA_DIR —
# regardless of the CWD the command is run from (commands run from pipeline/).
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
os.environ.setdefault("MILMAP_RAW_DIR", str(DATA_DIR / "raw"))
os.environ.setdefault("MILMAP_DB", str(DATA_DIR / "milmap.duckdb"))
DEFAULT_MASK = DATA_DIR / "fixtures" / "ukraine_adm0.geojson"

app = typer.Typer(no_args_is_help=True, add_completion=False)
ingest_app = typer.Typer(no_args_is_help=True, help="Fetch + normalize sources into the warehouse")
app.add_typer(ingest_app, name="ingest")


def parse_day(s: str) -> int:
    return int(s) if s.lstrip("-").isdigit() else day_index(date.fromisoformat(s))


@app.command()
def schema(out: Path = typer.Option(..., help="Directory for JSON Schema files")) -> None:
    """Export JSON Schema for the web contract (Manifest, DayBundle)."""
    out.mkdir(parents=True, exist_ok=True)
    for name, model in EXPORT_MODELS.items():
        s = _strip_property_titles(model.model_json_schema(mode="serialization"))
        (out / f"{name}.schema.json").write_bytes(orjson.dumps(s, option=orjson.OPT_INDENT_2))
        typer.echo(f"wrote {out / f'{name}.schema.json'}")


def _strip_property_titles(node):
    """Pydantic titles every field; json-schema-to-typescript would then emit an alias
    per field (`type Date = string` ...). Keep titles only on models/enums."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for p in props.values():
                _drop_titles_deep(p)
        for v in node.values():
            _strip_property_titles(v)
    elif isinstance(node, list):
        for v in node:
            _strip_property_titles(v)
    return node


def _drop_titles_deep(node) -> None:
    if isinstance(node, dict):
        if "$ref" not in node:
            node.pop("title", None)
        for k, v in node.items():
            if k != "properties":
                _drop_titles_deep(v)
    elif isinstance(node, list):
        for v in node:
            _drop_titles_deep(v)


@ingest_app.command("isw-map")
def ingest_isw_map(
    from_: str = typer.Option(..., "--from", help="First day (YYYY-MM-DD or day index)"),
    to: str = typer.Option(..., "--to", help="Last day (YYYY-MM-DD or day index)"),
) -> None:
    """Fetch ISW ArcGIS control-of-terrain for a day range into control_snapshot."""
    from .db import connect, store_snapshot
    from .geo.diff import area_km2
    from .sources.isw_arcgis import IswArcgisSource

    d0, d1 = parse_day(from_), parse_day(to)
    con = connect()
    try:
        n = 0
        for snap in IswArcgisSource().snapshots(d0, d1):
            km2 = area_km2(snap.geometry)
            store_snapshot(
                con,
                source_id=snap.source_id,
                category=snap.category,
                day=snap.day,
                geom=snap.geometry,
                area_km2=km2,
                meta=snap.meta,
            )
            n += 1
            typer.echo(f"  {snap.category:24s} {day_to_date(snap.day)}  {km2:10.1f} km2")
        typer.echo(f"ingested {n} control snapshots for days {d0}..{d1}")
    finally:
        con.close()


@app.command()
def export(
    out: Path = typer.Option(DATA_DIR / "build", help="Output dir (manifest.json + days/)"),
    temporal: bool = typer.Option(False, help="Also write temporal/*.geojsonl for tippecanoe"),
    mask: Path = typer.Option(DEFAULT_MASK, help="Ukraine adm0 GeoJSON used as the front mask"),
) -> None:
    """Build the static web bundle from the warehouse (control_snapshot)."""
    import json

    from shapely.geometry import shape

    from .db import connect
    from .export import build, build_input_from_db

    ukr = shape(json.loads(mask.read_text())["features"][0]["geometry"])
    con = connect()
    try:
        inp = build_input_from_db(con, ukr.boundary)
    finally:
        con.close()
    m = build(inp, out, temporal=temporal)
    typer.echo(
        f"wrote {out}: days {m.day_min}-{m.day_max}, {len(m.layers)} layers, synthetic={m.synthetic}"
    )


@app.command("isw-discover")
def isw_discover() -> None:
    """Print candidate ISW layers and how config/isw_layer_map.yaml classifies them."""
    from .sources.isw_arcgis import IswArcgisSource

    for svc, lid, lname, cat in IswArcgisSource().discover():
        flag = "" if cat else "   <-- UNCLASSIFIED"
        typer.echo(f"{svc:55s} {lid:>3} {lname:45s} {cat or '-'}{flag}")


if __name__ == "__main__":
    app()
