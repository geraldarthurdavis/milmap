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

Dates accept YYYY-MM-DD or day index. Implemented here: isw-discover, schema.
The rest are wired in PROMPT.md's build plan.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import orjson
import typer

from .models import EXPORT_MODELS
from .timeutil import day_index

app = typer.Typer(no_args_is_help=True, add_completion=False)


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


@app.command("isw-discover")
def isw_discover() -> None:
    """Print candidate ISW layers and how config/isw_layer_map.yaml classifies them."""
    from .sources.isw_arcgis import IswArcgisSource

    for svc, lid, lname, cat in IswArcgisSource().discover():
        flag = "" if cat else "   <-- UNCLASSIFIED"
        typer.echo(f"{svc:55s} {lid:>3} {lname:45s} {cat or '-'}{flag}")


if __name__ == "__main__":
    app()
