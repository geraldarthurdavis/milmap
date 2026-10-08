"""Source adapter contract.

Every source produces one or both of:
  * ControlSnapshot — an area layer for one day (ISW timelapse, DeepState)
  * Document        — text to run through extraction (ISW report, TG post, RSS item)

Adapters are pure fetch+normalize. They never geocode, never call the LLM and
never decide what is "true"; that is extract/ and fuse.py. Every raw response is
written under data/raw/<source>/ before parsing so a parser fix can be replayed
without re-fetching (`milmap ingest --replay`).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx
from shapely.geometry.base import BaseGeometry
from tenacity import retry, stop_after_attempt, wait_exponential

RAW_DIR = Path(os.environ.get("MILMAP_RAW_DIR", "data/raw"))


@dataclass
class ControlSnapshot:
    source_id: str
    category: str  # models.ControlCategory value
    day: int
    geometry: BaseGeometry  # EPSG:4326, valid, unioned
    meta: dict = field(default_factory=dict)


@dataclass
class Section:
    heading: str
    paragraphs: list[str]


@dataclass
class Document:
    source_id: str
    url: str
    day: int  # day the document is *about* (ISW: assessment date)
    published_at: datetime | None
    title: str
    language: str
    sections: list[Section]
    footnotes: dict[str, list[str]] = field(default_factory=dict)  # "12" -> [urls]

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.source_id}|{self.url}".encode()).hexdigest()[:16]

    @property
    def text(self) -> str:
        return "\n\n".join(
            f"## {s.heading}\n" + "\n".join(s.paragraphs) if s.heading else "\n".join(s.paragraphs)
            for s in self.sections
        )


class ControlSource(Protocol):
    source_id: str

    def snapshots(self, day_from: int, day_to: int) -> Iterator[ControlSnapshot]: ...


class DocumentSource(Protocol):
    source_id: str

    def documents(self, day_from: int, day_to: int) -> Iterator[Document]: ...


def http_client() -> httpx.Client:
    contact = os.environ.get("MILMAP_CONTACT", "unset")
    return httpx.Client(
        timeout=httpx.Timeout(60.0, connect=15.0),
        headers={"User-Agent": f"milmap/0.1 (+research; contact: {contact})"},
        follow_redirects=True,
        http2=False,
    )


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30), reraise=True)
def get_json(client: httpx.Client, url: str, params: dict | None = None) -> dict:
    r = client.get(url, params=params)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30), reraise=True)
def get_text(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def save_raw(source_id: str, key: str, content: str | bytes) -> Path:
    p = RAW_DIR / source_id / key
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_bytes(content)
    return p
