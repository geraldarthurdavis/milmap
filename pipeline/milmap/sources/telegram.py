"""Telegram public channels (milblogs, official, OSINT) via Telethon (MTProto).

Needs a *user* session (api_id/api_hash from my.telegram.org); bots cannot read
arbitrary channels. Public channels only; text only (media metadata kept, media
not downloaded). Incremental: resumes from the highest message id stored per
channel. Messages are mostly Russian/Ukrainian — translation happens inside the
extraction call, not here.

Telethon v1 is in maintenance mode but stable; isolate it behind this module.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..timeutil import telegram_day
from .base import Document, Section

CONFIG = Path(__file__).resolve().parents[2] / "config" / "telegram_channels.yaml"


@dataclass
class Channel:
    handle: str
    side: str
    reliability: str
    language: str
    kind: str


def load_channels(path: Path = CONFIG) -> list[Channel]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [Channel(**c) for c in raw.get("channels", [])]


async def fetch_channel(
    channel: Channel, min_id: int = 0, limit: int = 500
) -> AsyncIterator[tuple[int, Document]]:
    from telethon import TelegramClient  # imported lazily: optional at runtime

    client = TelegramClient(
        os.environ.get("TELEGRAM_SESSION", "data/milmap.session"),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
    )
    async with client:
        async for msg in client.iter_messages(channel.handle, min_id=min_id, reverse=True, limit=limit):
            text = (msg.message or "").strip()
            if len(text) < 40:  # stickers, one-liners, emoji
                continue
            yield (
                msg.id,
                Document(
                    source_id=f"tg:{channel.handle}",
                    url=f"https://t.me/{channel.handle}/{msg.id}",
                    day=telegram_day(msg.date),
                    published_at=msg.date,
                    title="",
                    language=channel.language,
                    sections=[Section("", [text])],
                ),
            )
