"""Place-name resolution: "Pishchane" -> (lon, lat), robust to transliteration.

Data: GeoNames country dumps (CC BY 4.0) — UA.txt plus RU filtered to the border
oblasts (Kursk, Belgorod, Bryansk, Rostov, Voronezh). Feature class P (populated
places) and selected T/H (heights, rivers) features. GeoNames' `alternatenames`
column carries Ukrainian/Russian/English spellings.

Resolution = fuzzy name match on a normalised key
           + oblast agreement (if the text gave one)
           + spatial prior: distance to the current front line
             (the same name can exist 10+ times in Ukraine; the one 4 km from
             the front is almost always meant).
"""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process
from unidecode import unidecode

# Collapse common UA/RU transliteration variants to one key.
_SUBS = [
    (r"['’`ʹʼ]", ""),
    (r"kh", "h"),
    (r"zh", "z"),
    (r"(ts|tz|c)", "ts"),
    (r"(yi|yy|iy|ij|yj|ii)", "i"),
    (r"(ya|ia)", "a"),
    (r"(yu|iu)", "u"),
    (r"(ye|ie|je)", "e"),
    (r"(yo|io|jo)", "o"),
    (r"y", "i"),
    (r"g", "h"),  # Russian g ~ Ukrainian h (Gorlovka/Horlivka)
    (r"[^a-z]", ""),
]
_SUBS_RE = [(re.compile(p), r) for p, r in _SUBS]

FEATURE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLX", "PPLL", "PPLF", "PPLH"}


def norm(name: str) -> str:
    s = unidecode(name).lower()
    for pat, rep in _SUBS_RE:
        s = pat.sub(rep, s)
    return s


@dataclass(frozen=True)
class Place:
    gid: str
    name: str
    lon: float
    lat: float
    admin1: str
    population: int


@dataclass
class Match:
    place: Place
    score: float  # 0..1


class Gazetteer:
    def __init__(self, places: list[Place]):
        self.places = places
        self.by_key: dict[str, list[Place]] = defaultdict(list)
        for p in places:
            self.by_key[norm(p.name)].append(p)
        self._keys = list(self.by_key)

    @classmethod
    def from_geonames(cls, paths: list[Path], alt_names: bool = True) -> Gazetteer:
        places: list[Place] = []
        csv.field_size_limit(10_000_000)
        for path in paths:
            with path.open(encoding="utf-8") as fh:
                for row in csv.reader(fh, delimiter="\t"):
                    if len(row) < 19 or row[6] != "P" or row[7] not in FEATURE_CODES:
                        continue
                    base = Place(
                        f"geonames:{row[0]}", row[2], float(row[5]), float(row[4]), row[10], int(row[14] or 0)
                    )
                    places.append(base)
                    if alt_names:
                        for alt in {a for a in row[3].split(",") if a and a.isascii()}:
                            places.append(
                                Place(base.gid, alt, base.lon, base.lat, base.admin1, base.population)
                            )
        return cls(places)

    def candidates(self, name: str, limit: int = 8, cutoff: float = 85) -> list[Match]:
        key = norm(name)
        hits = process.extract(key, self._keys, scorer=fuzz.ratio, limit=limit, score_cutoff=cutoff)
        out: dict[str, Match] = {}
        for k, score, _ in hits:
            for p in self.by_key[k]:
                m = out.get(p.gid)
                if m is None or m.score < score / 100:
                    out[p.gid] = Match(p, score / 100)
        return sorted(out.values(), key=lambda m: -m.score)

    def resolve(
        self,
        name: str,
        *,
        admin1: str | None = None,
        near: tuple[float, float] | None = None,
        front_distance_km=None,  # callable (lon, lat) -> km, from the day's front lines
    ) -> Match | None:
        best: tuple[float, Match] | None = None
        for m in self.candidates(name):
            s = m.score
            if admin1 and m.place.admin1 == admin1:
                s += 0.15
            if front_distance_km is not None:
                d = front_distance_km(m.place.lon, m.place.lat)
                s += 0.3 * math.exp(-d / 25.0)  # strongly prefer places near the front
            if near is not None:
                s += 0.1 * math.exp(-_km(near, (m.place.lon, m.place.lat)) / 50.0)
            if best is None or s > best[0]:
                best = (s, m)
        return best[1] if best else None


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


BEARINGS = {
    "north_of": 0,
    "northeast_of": 45,
    "east_of": 90,
    "southeast_of": 135,
    "south_of": 180,
    "southwest_of": 225,
    "west_of": 270,
    "northwest_of": 315,
}


def offset(lon: float, lat: float, relation: str, km: float) -> tuple[float, float]:
    """Displace an anchor by `relation` (e.g. north_of) and distance (default 2 km)."""
    if relation not in BEARINGS:
        return lon, lat
    km = km or 2.0
    b = math.radians(BEARINGS[relation])
    dlat = km * math.cos(b) / 111.32
    dlon = km * math.sin(b) / (111.32 * math.cos(math.radians(lat)))
    return lon + dlon, lat + dlat
