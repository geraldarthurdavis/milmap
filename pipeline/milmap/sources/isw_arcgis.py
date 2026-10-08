"""ISW control-of-terrain from ArcGIS Online FeatureServers (daily history).

Flow:
  discover services -> keep timelapse-like ones -> list layers -> classify by name
  -> page through `query?f=geojson` -> group by ISW day (datetime -> ET date)
  -> union per (category, day) -> ControlSnapshot

Etiquette: pages of <=2000 features, ~1 req/s, raw pages cached under
data/raw/isw_arcgis/. These are ISW/CTP products — see docs/LICENSING.md before
publishing derived layers publicly.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import shapely
import yaml
from shapely.geometry import shape
from shapely.ops import unary_union

from ..timeutil import day_to_date, isw_day
from .base import ControlSnapshot, get_json, http_client, save_raw

CONFIG = Path(__file__).resolve().parents[2] / "config" / "isw_layer_map.yaml"


@dataclass
class LayerRule:
    pattern: re.Pattern[str]
    category: str | None


@dataclass
class IswConfig:
    base_url: str
    service_include: list[re.Pattern[str]]
    service_exclude: list[re.Pattern[str]]
    time_field: str
    layer_rules: list[LayerRule]

    @classmethod
    def load(cls, path: Path = CONFIG) -> IswConfig:
        raw = yaml.safe_load(path.read_text())
        return cls(
            base_url=raw["base_url"].rstrip("/"),
            service_include=[re.compile(p) for p in raw["service_include"]],
            service_exclude=[re.compile(p) for p in raw["service_exclude"]],
            time_field=raw["time_field"],
            layer_rules=[LayerRule(re.compile(r["match"]), r["category"]) for r in raw["layer_rules"]],
        )

    def wants_service(self, name: str) -> bool:
        return any(p.search(name) for p in self.service_include) and not any(
            p.search(name) for p in self.service_exclude
        )

    def classify(self, layer_name: str) -> str | None:
        for rule in self.layer_rules:
            if rule.pattern.search(layer_name):
                return rule.category
        return None


class IswArcgisSource:
    source_id = "isw"

    def __init__(
        self, cfg: IswConfig | None = None, client: httpx.Client | None = None, delay_s: float = 1.0
    ):
        self.cfg = cfg or IswConfig.load()
        self.client = client or http_client()
        self.delay_s = delay_s

    # ---- discovery
    def services(self) -> list[str]:
        data = get_json(self.client, self.cfg.base_url, {"f": "json"})
        return [s["name"] for s in data.get("services", []) if s.get("type") == "FeatureServer"]

    def layers(self, service: str) -> list[tuple[int, str]]:
        data = get_json(self.client, f"{self.cfg.base_url}/{service}/FeatureServer", {"f": "json"})
        return [(lyr["id"], lyr["name"]) for lyr in data.get("layers", [])]

    def discover(self) -> list[tuple[str, int, str, str | None]]:
        """(service, layer_id, layer_name, category) for every candidate layer."""
        out = []
        for svc in self.services():
            if not self.cfg.wants_service(svc):
                continue
            for lid, lname in self.layers(svc):
                out.append((svc, lid, lname, self.cfg.classify(lname)))
            time.sleep(self.delay_s)
        return out

    # ---- features
    def query(self, service: str, layer_id: int, where: str = "1=1") -> Iterator[dict]:
        url = f"{self.cfg.base_url}/{service}/FeatureServer/{layer_id}/query"
        offset, page = 0, 2000
        while True:
            params = {
                "where": where,
                "outFields": f"OBJECTID,{self.cfg.time_field}",
                "returnGeometry": "true",
                "outSR": "4326",
                "geometryPrecision": "5",
                "orderByFields": "OBJECTID",
                "resultOffset": str(offset),
                "resultRecordCount": str(page),
                "f": "geojson",
            }
            data = get_json(self.client, url, params)
            save_raw(self.source_id, f"{service}/{layer_id}/{offset:07d}.geojson", json.dumps(data))
            feats = data.get("features", [])
            yield from feats
            exceeded = data.get("exceededTransferLimit") or data.get("properties", {}).get(
                "exceededTransferLimit"
            )
            if not feats or (not exceeded and len(feats) < page):
                return
            offset += len(feats)
            time.sleep(self.delay_s)

    def snapshots(self, day_from: int, day_to: int) -> Iterator[ControlSnapshot]:
        tf = self.cfg.time_field
        # ISW stamps ~20:00 UTC; pad a day either side, then filter by ET date.
        lo = day_to_date(day_from - 1).isoformat()
        hi = day_to_date(day_to + 1).isoformat()
        where = f"{tf} >= DATE '{lo}' AND {tf} <= DATE '{hi}'"
        buckets: dict[tuple[str, int], list] = defaultdict(list)
        provenance: dict[tuple[str, int], set[str]] = defaultdict(set)
        for svc, lid, _lname, cat in self.discover():
            if cat is None:
                continue
            for f in self.query(svc, lid, where):
                ts = (f.get("properties") or {}).get(tf)
                if ts is None or f.get("geometry") is None:
                    continue
                day = isw_day(ts)
                if not day_from <= day <= day_to:
                    continue
                buckets[(cat, day)].append(shape(f["geometry"]))
                provenance[(cat, day)].add(f"{svc}/{lid}")
        for (cat, day), geoms in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            g = shapely.make_valid(unary_union([shapely.make_valid(x) for x in geoms]))
            yield ControlSnapshot("isw", cat, day, g, {"layers": sorted(provenance[(cat, day)])})
