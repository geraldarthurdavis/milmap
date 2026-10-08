"""Canonical data model — the single source of truth for the pipeline <-> web contract.

`milmap schema` exports JSON Schema for the *export* models (Manifest, DayBundle and
everything they reference) to packages/schema/schema/, from which TypeScript types
are generated. Change a model here, run `pnpm schema:gen`, commit both.

Conventions
  * JSON is snake_case on both sides.
  * Geometry is GeoJSON, EPSG:4326, [lon, lat], coordinates rounded to 5 dp (~1 m).
  * `day` is the integer day index (see timeutil.py); `date` is ISO YYYY-MM-DD.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        # Exports always write every field (nulls included), so the contract marks
        # defaulted fields as required and TS never sees `x?: T | null`.
        json_schema_serialization_defaults_required=True,
    )


# ---------------------------------------------------------------- vocabularies


class SourceKind(StrEnum):
    analytic = "analytic"  # ISW, think tanks: assessed, footnoted
    osint_map = "osint_map"  # DeepState and similar maps
    milblog = "milblog"  # RU/UA military bloggers (claims)
    official = "official"  # MoD / General Staff
    telegram = "telegram"  # generic TG channel (aggregators, units)
    news = "news"


class Reliability(StrEnum):
    """NATO/Admiralty source-reliability grade (AJP-2.1). Assigned per *source*."""

    A = "A"  # completely reliable
    B = "B"  # usually reliable
    C = "C"  # fairly reliable
    D = "D"  # not usually reliable
    E = "E"  # unreliable
    F = "F"  # reliability cannot be judged


class Actor(StrEnum):
    RU = "RU"
    UA = "UA"
    unknown = "unknown"


class Status(StrEnum):
    """Epistemic status of a single observation — drives line/marker style."""

    assessed = "assessed"  # analyst assessment (ISW "assessed")
    geolocated = "geolocated"  # footage geolocated by the source
    claimed = "claimed"  # a party claims it (milblogger, MoD)
    reported = "reported"  # reported without claim of verification
    denied = "denied"  # explicitly refuted by another source


class ObservationKind(StrEnum):
    advance = "advance"
    withdrawal = "withdrawal"
    seizure = "seizure"  # claimed/assessed capture of a settlement
    infiltration = "infiltration"
    assault = "assault"  # offensive operations, no change in control
    counterattack = "counterattack"
    strike = "strike"  # long-range / drone / artillery strike
    unit_presence = "unit_presence"
    other = "other"


class ControlCategory(StrEnum):
    """Area layers, mirroring ISW's legend plus DeepState's."""

    assessed_control = "assessed_control"  # assessed Russian-controlled
    pre_2022 = "pre_2022"  # occupied before 2022-02-24 (Crimea, ORDLO)
    assessed_advance = "assessed_advance"  # assessed Russian advances
    assessed_infiltration = "assessed_infiltration"  # assessed RU infiltration areas
    claimed_control = "claimed_control"  # claimed Russian control
    claimed_ua_counter = "claimed_ua_counter"  # claimed UA counteroffensives
    ua_in_russia = "ua_in_russia"  # UA-held Russian territory (e.g. Kursk 2024-25)
    contested = "contested"  # DeepState "grey zone"


class LineKind(StrEnum):
    front = "front"  # boundary of assessed control, interior to Ukraine only
    advance_limit = "advance_limit"  # outer edge of assessed advances
    claimed_limit = "claimed_limit"  # outer edge of claimed control
    infiltration_limit = "infiltration_limit"


# ---------------------------------------------------------------- sources


class Source(_Model):
    id: str = Field(description="Stable slug, e.g. 'isw', 'deepstate', 'tg:rybar'")
    name: str
    kind: SourceKind
    side: Actor = Field(description="Which side the source is aligned with (unknown = neutral)")
    reliability: Reliability
    url: str
    language: str = "en"
    license_note: str = Field(description="Terms the data is used under; shown in attribution")


# ---------------------------------------------------------------- geometry

Position = list[float]


class PointGeometry(_Model):
    type: Literal["Point"] = "Point"
    coordinates: Position


class Feature(_Model):
    """Loose GeoJSON Feature (geometry left untyped to keep the TS side simple)."""

    type: Literal["Feature"] = "Feature"
    id: str | int | None = None
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)


class FeatureCollection(_Model):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature] = Field(default_factory=list)


# ---------------------------------------------------------------- observations


class PlaceRef(_Model):
    name: str = Field(description="Name as written in the source")
    gazetteer_id: str | None = Field(None, description="e.g. 'geonames:704508'")
    canonical_name: str | None = Field(None, description="ISW-style transliteration")
    relation: str = Field("in", description="in | near | north_of | ... | between")
    distance_km: float | None = None
    resolution_confidence: float = Field(0.0, ge=0, le=1)


class Citation(_Model):
    source_id: str
    url: str
    published_at: str | None = None
    excerpt: str | None = Field(
        None, max_length=300, description="<=25 words verbatim; never republish full text"
    )


class Observation(_Model):
    id: str = Field(description="sha1 of (source_id, document_id, ordinal)")
    day: int
    date: str
    source_id: str
    kind: ObservationKind
    actor: Actor
    status: Status
    place: PlaceRef
    geometry: PointGeometry | None = Field(None, description="Resolved anchor point")
    front_anchor: PointGeometry | None = Field(
        None, description="Nearest point on that day's front line (for callout leader lines)"
    )
    axis: str | None = Field(None, description="Operational direction, e.g. 'Pokrovsk direction'")
    units: list[str] = Field(default_factory=list)
    summary: str = Field(max_length=280, description="Our own paraphrase, English")
    citations: list[Citation] = Field(default_factory=list)
    credibility: int = Field(6, ge=1, le=6, description="Admiralty information credibility 1..6")
    cluster_id: str | None = Field(None, description="Fusion cluster (same place/day/kind)")
    corroboration: int = Field(1, ge=1, description="Independent sources in the cluster")
    conflicts_with_assessment: bool = Field(
        False, description="Claim lies outside the assessed-control area for the day"
    )


# ---------------------------------------------------------------- exports


class LayerFormat(StrEnum):
    bundle = "bundle"  # inside days/{date}.json
    temporal_pmtiles = "temporal_pmtiles"  # one archive, features carry vf/vt day range


class LayerDescriptor(_Model):
    id: str = Field(description="e.g. 'isw.assessed_control', 'deepstate.front'")
    source_id: str
    geom: Literal["area", "line", "point"]
    category: str = Field(description="ControlCategory / LineKind / 'observations'")
    format: LayerFormat = LayerFormat.bundle
    url: str | None = Field(None, description="For temporal_pmtiles: archive URL")
    source_layer: str | None = None
    day_ranges: list[tuple[int, int]] = Field(
        default_factory=list, description="Inclusive [from, to] day ranges with data"
    )


class DayStat(_Model):
    day: int
    ru_gain_km2: float = 0.0
    ua_gain_km2: float = 0.0
    observations: int = 0
    claims: int = 0


class Manifest(_Model):
    version: Literal[1] = 1
    epoch: str = "2022-02-24"
    generated_at: str
    synthetic: bool = Field(False, description="True for demo fixtures; UI shows a banner")
    day_min: int
    day_max: int
    sources: list[Source]
    layers: list[LayerDescriptor]
    stats: list[DayStat] = Field(description="One entry per day in [day_min, day_max]")
    bundle_url_template: str = "days/{date}.json"


class DayBundle(_Model):
    day: int
    date: str
    layers: dict[str, FeatureCollection] = Field(
        description="layer id -> FeatureCollection; areas, lines and diff polygons"
    )
    observations: list[Observation] = Field(default_factory=list)


EXPORT_MODELS: dict[str, type[BaseModel]] = {
    "manifest": Manifest,
    "day_bundle": DayBundle,
}
