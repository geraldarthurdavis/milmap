"""Multi-source fusion: many observations -> clusters with corroboration & conflicts.

Not truth-finding. The map shows *who says what*; fusion only:
  1. clusters observations about the same place (gazetteer id or <=1.5 km) and
     compatible kind within +-1 day,
  2. counts independent sources (distinct source_id, and distinct *sides* count
     double — a RU milblogger and UA General Staff agreeing is strong),
  3. upgrades Admiralty credibility when corroborated (1 = confirmed by other
     independent sources ... 6 = cannot be judged),
  4. flags claims that fall outside the same day's assessed-control polygon
     (`conflicts_with_assessment`) — the "claimed vs assessed" gap ISW maps show.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable

from .models import Observation

COMPATIBLE = {
    "advance": {"advance", "seizure", "infiltration"},
    "seizure": {"advance", "seizure"},
    "infiltration": {"advance", "infiltration"},
    "withdrawal": {"withdrawal", "counterattack"},
    "counterattack": {"withdrawal", "counterattack"},
}

STATUS_BASE_CRED = {"assessed": 2, "geolocated": 2, "reported": 4, "claimed": 5, "denied": 6}


def _km(a, b) -> float:
    (lon1, lat1), (lon2, lat2) = a, b
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371.0 * math.hypot(x, y)


def _same_place(a: Observation, b: Observation) -> bool:
    if a.place.gazetteer_id and a.place.gazetteer_id == b.place.gazetteer_id:
        return True
    if a.geometry and b.geometry:
        return _km(a.geometry.coordinates, b.geometry.coordinates) <= 1.5
    return False


def _compatible(a: Observation, b: Observation) -> bool:
    return a.actor == b.actor and b.kind in COMPATIBLE.get(a.kind, {a.kind})


def fuse(
    obs: list[Observation],
    source_side: dict[str, str],
    in_assessed_control: Callable[[int, tuple[float, float]], bool] | None = None,
) -> list[Observation]:
    obs = sorted(obs, key=lambda o: (o.day, o.id))
    clusters: list[list[Observation]] = []
    for o in obs:
        for c in clusters:
            head = c[0]
            if abs(o.day - head.day) <= 1 and _same_place(o, head) and _compatible(o, head):
                c.append(o)
                break
        else:
            clusters.append([o])

    out = []
    for c in clusters:
        cid = hashlib.sha1("|".join(sorted(x.id for x in c)).encode()).hexdigest()[:12]
        sources = {x.source_id for x in c}
        sides = {source_side.get(s, "unknown") for s in sources}
        corroboration = len(sources) + (1 if len(sides - {"unknown"}) > 1 else 0)
        for x in c:
            cred = STATUS_BASE_CRED.get(x.status, 6)
            if corroboration >= 3:
                cred = 1 if x.status in ("assessed", "geolocated") else min(cred, 2)
            elif corroboration == 2:
                cred = max(1, cred - 1)
            conflicts = False
            if (
                in_assessed_control is not None
                and x.status == "claimed"
                and x.actor == "RU"
                and x.kind in ("advance", "seizure")
                and x.geometry is not None
            ):
                conflicts = not in_assessed_control(x.day, tuple(x.geometry.coordinates))
            out.append(
                x.model_copy(
                    update={
                        "cluster_id": cid,
                        "corroboration": corroboration,
                        "credibility": cred,
                        "conflicts_with_assessment": conflicts,
                    }
                )
            )
    return out
