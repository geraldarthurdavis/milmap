"""Text -> ExtractedEvent[] with Claude structured outputs.

* Online (daily): `client.messages.parse(..., output_format=ExtractionResult)`.
* Backfill (thousands of report sections): Message Batches API (50% cheaper);
  build requests with the raw JSON schema in `output_config.format`.
* Cached by sha1(model, prompt version, section text) in DuckDB so reruns are free.
* Chunk by report *section* (direction headings) — keeps `axis` context and
  keeps each call small enough to avoid max_tokens truncation.
"""

from __future__ import annotations

import hashlib
import os

from anthropic import Anthropic

from ..sources.base import Document, Section
from .prompts import SYSTEM, USER_TEMPLATE
from .schema import ExtractionResult

PROMPT_VERSION = "2026-10-07.1"
DEFAULT_MODEL = os.environ.get("MILMAP_EXTRACT_MODEL", "claude-sonnet-5-5")


def cache_key(model: str, text: str) -> str:
    return hashlib.sha1(f"{model}|{PROMPT_VERSION}|{text}".encode()).hexdigest()


def render(doc: Document, section: Section, source_name: str, source_kind: str, reliability: str) -> str:
    from ..timeutil import day_to_date

    return USER_TEMPLATE.format(
        source_name=source_name,
        source_kind=source_kind,
        reliability=reliability,
        date=day_to_date(doc.day).isoformat(),
        heading=section.heading or "(none)",
        text="\n\n".join(section.paragraphs),
    )


def extract_section(client: Anthropic, user_prompt: str, model: str = DEFAULT_MODEL) -> ExtractionResult:
    resp = client.messages.parse(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=ExtractionResult,
    )
    if resp.stop_reason in ("refusal", "max_tokens") or resp.parsed_output is None:
        raise RuntimeError(f"extraction failed: stop_reason={resp.stop_reason}")
    return resp.parsed_output


def batch_request(custom_id: str, user_prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """One entry for client.messages.batches.create(requests=[...])."""
    return {
        "custom_id": custom_id,
        "params": {
            "model": model,
            "max_tokens": 8000,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": user_prompt}],
            "output_config": {
                "format": {"type": "json_schema", "schema": strict_schema()},
            },
        },
    }


def strict_schema() -> dict:
    """ExtractionResult JSON Schema with additionalProperties:false everywhere."""
    schema = ExtractionResult.model_json_schema()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema
