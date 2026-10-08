"""DeepState occupied-territory history via the community mirror
github.com/cyterat/deepstate-map-data (GPL-3.0 repo; daily at ~03:00 UTC).

`deepstate-map-data.geojson.gz` holds every day as {id, date, geometry}.
Treat DeepState as a second *assessed_control* opinion (source_id 'deepstate'),
never merged with ISW — the UI compares them.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from datetime import date

import shapely
from shapely.geometry import shape

from ..timeutil import day_index
from .base import ControlSnapshot, http_client, save_raw

URL = "https://raw.githubusercontent.com/cyterat/deepstate-map-data/main/deepstate-map-data.geojson.gz"


class DeepStateSource:
    source_id = "deepstate"

    def __init__(self, url: str = URL):
        self.url = url

    def snapshots(self, day_from: int, day_to: int) -> Iterator[ControlSnapshot]:
        with http_client() as c:
            r = c.get(self.url)
            r.raise_for_status()
            blob = r.content
        save_raw(self.source_id, "deepstate-map-data.geojson.gz", blob)
        fc = json.loads(gzip.decompress(blob))
        for f in sorted(fc["features"], key=lambda f: f["properties"]["date"]):
            d = day_index(date.fromisoformat(f["properties"]["date"][:10]))
            if day_from <= d <= day_to:
                g = shapely.make_valid(shape(f["geometry"]))
                yield ControlSnapshot(self.source_id, "assessed_control", d, g)
