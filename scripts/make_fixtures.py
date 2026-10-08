"""Generate SYNTHETIC demo data so the web app runs with zero network/API keys.

    cd pipeline && uv run python ../scripts/make_fixtures.py --out ../data/build

Geography is real (Natural Earth Ukraine outline); the front line, areas and
events are invented and deterministic. manifest.synthetic = true, so the UI
shows a "SYNTHETIC DEMO DATA" banner. Never deploy fixtures publicly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box, shape

from milmap.export import BuildInput, build
from milmap.geo.frontline import front_lines, nearest_on_lines
from milmap.models import (
    Citation,
    Observation,
    PlaceRef,
    PointGeometry,
    Source,
)
from milmap.timeutil import day_index, day_to_date

ROOT = Path(__file__).resolve().parents[1]
UKR = shape(json.loads((ROOT / "data/fixtures/ukraine_adm0.geojson").read_text())["features"][0]["geometry"])

# Invented front, north -> south-west. Each point: (lon, lat, drift_lon_per_90d, wobble)
FRONT = [
    (38.05, 50.36, 0.00, 0.00),
    (37.80, 50.05, 0.00, 0.02),
    (37.70, 49.75, 0.05, 0.03),  # "Kupyansk" sector — UA counterattacks push east
    (37.85, 49.35, 0.00, 0.02),
    (37.92, 49.02, -0.04, 0.02),
    (37.88, 48.80, -0.06, 0.02),
    (37.66, 48.56, -0.12, 0.03),  # "Kostyantynivka" sector — main RU effort
    (37.30, 48.36, -0.10, 0.03),
    (36.95, 48.08, -0.08, 0.02),
    (36.55, 47.82, -0.05, 0.02),
    (36.20, 47.62, -0.03, 0.02),
    (35.75, 47.48, 0.00, 0.01),
    (35.25, 47.42, 0.00, 0.01),
    (34.70, 47.48, 0.00, 0.00),  # reservoir / Dnipro
    (34.20, 47.30, 0.00, 0.00),
    (33.70, 46.95, 0.00, 0.00),
    (33.30, 46.76, 0.00, 0.00),
    (32.75, 46.62, 0.00, 0.00),
    (32.30, 46.48, 0.00, 0.00),
    (31.60, 46.40, 0.00, 0.00),
]

PRE_2022 = shapely.union_all(
    [
        UKR.intersection(box(32.3, 44.3, 36.8, 46.1)),  # Crimea (approx.)
        UKR.intersection(
            Polygon([(38.2, 47.1), (40.3, 47.1), (40.3, 48.9), (39.1, 48.9), (38.6, 48.3), (38.3, 47.8)])
        ),  # ORDLO (approx.)
    ]
)

TOWNS = {  # real names, invented events
    "Kupyansk": (37.61, 49.71),
    "Borova": (37.62, 49.38),
    "Lyman": (37.80, 48.99),
    "Siversk": (38.10, 48.87),
    "Kostyantynivka": (37.71, 48.53),
    "Druzhkivka": (37.53, 48.63),
    "Pokrovsk": (37.18, 48.28),
    "Dobropillia": (37.08, 48.47),
    "Velykomykhailivka": (36.80, 48.05),
    "Huliaipole": (36.26, 47.66),
    "Orikhiv": (35.79, 47.57),
    "Stepnohirsk": (35.48, 47.58),
}


def front_points(t: int, n_days: int, jitter: float = 0.0) -> list[tuple[float, float]]:
    f = t / max(1, n_days - 1)
    pts = []
    for i, (lon, lat, drift, wob) in enumerate(FRONT):
        noise = wob * math.sin(t / 6.0 + i * 1.7) * 0.5 + jitter * math.sin(t / 3.1 + i)
        pts.append((lon + drift * f + noise, lat + 0.3 * noise))
    return pts


def control_from_front(pts: list[tuple[float, float]]) -> Polygon:
    ring = [*pts, (31.0, 46.35), (31.0, 43.5), (41.5, 43.5), (41.5, 50.6), (pts[0][0], 50.6)]
    return shapely.make_valid(Polygon(ring)).intersection(UKR)


def band(line: LineString, side_area, km: float, sector: tuple[int, int]) -> Polygon:
    """Area within `km` of a front sector, on the side *outside* side_area."""
    i0, i1 = sector
    seg = LineString(list(line.coords)[i0 : i1 + 1])
    return seg.buffer(km / 111.0).difference(side_area).intersection(UKR)


def obs_id(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data/build")
    ap.add_argument("--end", default="2026-10-06")
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()

    d_end = day_index(date.fromisoformat(args.end))
    days = list(range(d_end - args.days + 1, d_end + 1))
    areas: dict[tuple[str, str], dict[int, object]] = {}

    def put(src: str, cat: str, day: int, g) -> None:
        if g is not None and not g.is_empty:
            areas.setdefault((src, cat), {})[day] = g

    observations: list[Observation] = []
    names = list(TOWNS)
    for t, day in enumerate(days):
        pts = front_points(t, len(days))
        ctrl = control_from_front(pts).difference(PRE_2022)
        line = LineString(pts)
        full = shapely.union_all([ctrl, PRE_2022])
        put("isw", "pre_2022", day, PRE_2022)
        put("isw", "assessed_control", day, ctrl)
        put("isw", "assessed_advance", day, band(line, full, 2.5, (5, 9)))
        put("isw", "claimed_control", day, band(line, full, 6.0, (4, 11)))
        inf = (
            shapely.union_all(
                [
                    Point(pts[6][0] - 0.06, pts[6][1] + 0.01).buffer(0.025),
                    Point(pts[7][0] - 0.05, pts[7][1] - 0.02).buffer(0.018),
                ]
            )
            .difference(full)
            .intersection(UKR)
        )
        put("isw", "assessed_infiltration", day, inf)
        put(
            "isw",
            "claimed_ua_counter",
            day,
            Point(pts[2][0] + 0.05, pts[2][1]).buffer(0.04).intersection(full),
        )
        # A second opinion: DeepState-like control, slightly different line
        ds = control_from_front(front_points(t, len(days), jitter=0.015)).difference(PRE_2022)
        put("deepstate", "pre_2022", day, PRE_2022)
        put("deepstate", "assessed_control", day, ds)

        fronts = front_lines(full, UKR.boundary)
        for k in range(3 + (t % 4)):
            name = names[(t * 5 + k * 7) % len(names)]
            lon, lat = TOWNS[name]
            status = ["assessed", "geolocated", "claimed", "reported"][(t + k) % 4]
            src = {"claimed": "tg:synthetic_ru", "reported": "deepstate"}.get(status, "isw")
            kind = ["advance", "assault", "infiltration", "counterattack", "strike"][(t * 3 + k) % 5]
            actor = "UA" if kind == "counterattack" else "RU"
            anchor = nearest_on_lines(Point(lon, lat), fronts)
            observations.append(
                Observation(
                    id=obs_id(day, k, name),
                    day=day,
                    date=day_to_date(day).isoformat(),
                    source_id=src,
                    kind=kind,
                    actor=actor,
                    status=status,
                    place=PlaceRef(
                        name=name, canonical_name=name, relation="near", resolution_confidence=1.0
                    ),
                    geometry=PointGeometry(coordinates=[lon, lat]),
                    front_anchor=PointGeometry(coordinates=[round(anchor.x, 5), round(anchor.y, 5)])
                    if anchor
                    else None,
                    axis=f"{name} direction",
                    summary=f"SYNTHETIC: {actor} {kind} {status} near {name}.",
                    citations=[Citation(source_id=src, url="https://example.org/synthetic")],
                    credibility={"assessed": 2, "geolocated": 2, "claimed": 5, "reported": 4}[status],
                )
            )

    sources = [
        Source(
            id="isw",
            name="ISW (synthetic stand-in)",
            kind="analytic",
            side="unknown",
            reliability="B",
            url="https://understandingwar.org",
            license_note="Synthetic demo data",
        ),
        Source(
            id="deepstate",
            name="DeepState (synthetic stand-in)",
            kind="osint_map",
            side="UA",
            reliability="B",
            url="https://deepstatemap.live",
            license_note="Synthetic demo data",
        ),
        Source(
            id="tg:synthetic_ru",
            name="RU milblogger (synthetic)",
            kind="milblog",
            side="RU",
            reliability="D",
            url="https://t.me/",
            language="ru",
            license_note="Synthetic demo data",
        ),
    ]
    m = build(BuildInput(sources, areas, UKR.boundary, observations, synthetic=True), args.out, temporal=True)
    print(
        f"wrote {args.out}: days {m.day_min}-{m.day_max}, {len(m.layers)} layers, "
        f"{len(observations)} observations"
    )


if __name__ == "__main__":
    main()
