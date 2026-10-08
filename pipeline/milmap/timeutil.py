"""Canonical time model.

Every layer and observation is keyed by an integer *day index*: days since the
full-scale invasion (2022-02-24 = day 0). The web app uses the same epoch
(packages/schema/src/time.ts) so URLs, files and tiles agree.

"Which day does a datum belong to?" differs per source:
  * ISW assessments are dated in US Eastern time (reports say "Assessment as of
    8:30 PM ET"; ArcGIS `datetime` values land at 20:00 UTC = afternoon ET).
    -> convert the timestamp to America/New_York and take the calendar date.
  * Telegram / milblog posts are stamped in UTC; the war is fought on Kyiv time.
    -> convert to Europe/Kyiv and take the calendar date.
  * DeepState files are named by update date -> use as-is.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

EPOCH = date(2022, 2, 24)
ET = ZoneInfo("America/New_York")
KYIV = ZoneInfo("Europe/Kyiv")


def day_index(d: date) -> int:
    return (d - EPOCH).days


def day_to_date(day: int) -> date:
    return EPOCH + timedelta(days=day)


def local_date(ts: datetime, tz: ZoneInfo) -> date:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(tz).date()


def epoch_ms_to_datetime(ms: int | float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def isw_day(ms: int | float) -> int:
    """Day index for an ISW ArcGIS `datetime` (epoch ms, UTC)."""
    return day_index(local_date(epoch_ms_to_datetime(ms), ET))


def telegram_day(ts: datetime) -> int:
    return day_index(local_date(ts, KYIV))
