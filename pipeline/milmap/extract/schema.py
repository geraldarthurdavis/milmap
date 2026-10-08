"""What the LLM returns. Deliberately flat and all-required.

Structured outputs compile the schema to a grammar with hard limits (as of
2026-10: <=24 optional params and <=16 union-typed params per request; a
`str | None` counts as a union). So: no Optional fields — use "" / "unknown"
sentinels and enums instead. Coordinates are NOT requested: the model names
places; the gazetteer resolves them (models hallucinate coordinates).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal[
    "advance",
    "withdrawal",
    "seizure",
    "infiltration",
    "assault",
    "counterattack",
    "strike",
    "unit_presence",
    "other",
]
Status = Literal["assessed", "geolocated", "claimed", "reported", "denied"]
Actor = Literal["RU", "UA", "unknown"]
Relation = Literal[
    "in",
    "near",
    "north_of",
    "northeast_of",
    "east_of",
    "southeast_of",
    "south_of",
    "southwest_of",
    "west_of",
    "northwest_of",
    "between",
    "toward",
]


class ExtractedEvent(BaseModel):
    kind: Kind
    actor: Actor = Field(description="Side performing the action")
    status: Status = Field(
        description="assessed=analyst judgement; geolocated=footage geolocated; "
        "claimed=a party claims it; reported=stated without verification; denied=refuted"
    )
    place: str = Field(description="Settlement/feature name exactly as in the text, transliterated to Latin")
    relation: Relation = Field(description="Position relative to `place`")
    second_place: str = Field(description="For 'between'/'toward' only, else empty string")
    oblast: str = Field(description="Oblast if stated or unambiguous from context, else empty string")
    axis: str = Field(description="Operational direction heading, e.g. 'Pokrovsk direction', else empty")
    distance_km: float = Field(description="Stated distance from place in km, else 0")
    units: list[str] = Field(description="Military units named for this event (may be empty)")
    claimant: str = Field(
        description="Who claims/reports it (e.g. 'Russian milblogger', 'Ukrainian General Staff'), else empty"
    )
    summary: str = Field(description="One neutral English sentence, <=30 words, own words (no copying)")
    footnotes: list[str] = Field(description="Endnote numbers cited for this event, e.g. ['12','13']")
    evidence_quote: str = Field(description="Shortest verbatim span (<=25 words) supporting the event")


class ExtractionResult(BaseModel):
    events: list[ExtractedEvent]
