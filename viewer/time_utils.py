"""Timezone and timestamp helpers for the Tapo Viewer.

All viewer-facing timestamps use Asia/Ho_Chi_Minh (+07:00).
The recorder filenames are local NAS time and therefore become aware
timestamps in this module rather than remaining naive datetimes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def localize(dt: datetime) -> datetime:
    """Return an aware datetime in the viewer's canonical timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def iso_local(dt: datetime) -> str:
    """Return canonical ISO-8601 local time with explicit +07:00 offset."""
    return localize(dt).isoformat(timespec="seconds")


def parse_filename_start(date_str: str, time_str: str) -> datetime:
    """Parse recorder filename date/time as Asia/Ho_Chi_Minh."""
    return datetime.strptime(
        date_str + time_str, "%Y%m%d%H%M%S"
    ).replace(tzinfo=LOCAL_TZ)


def segment_end(start: datetime, duration: float) -> datetime:
    """Calculate an aware segment end without losing timezone information."""
    return localize(start) + timedelta(seconds=float(duration))
