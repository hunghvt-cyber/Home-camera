"""Viewer-side event -> recording segment resolver.

The resolver is deliberately independent of the recorder/Event Logger.
It consumes normalized segment metadata and raw JSONL event dictionaries.

Contract:
- segment start/end are ISO-8601 timestamps; explicit offsets are preferred.
- event timestamp is read from event_local first, then common timestamp keys.
- segment identity may be supplied by segment/file/path keys; timestamp matching
  remains the source of truth when the hint is absent or stale.
- interval semantics are [start, end): an event exactly at a segment end belongs
  to the following segment.
- unresolved events are returned, never guessed.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Iterable
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
EVENT_TIME_KEYS = ("event_local", "timestamp", "event_time", "time", "datetime")
SEGMENT_HINT_KEYS = ("relative_path", "file", "segment", "segment_file", "path")


def parse_timestamp(value: Any, *, default_tz: ZoneInfo = LOCAL_TZ) -> datetime | None:
    """Parse ISO-8601 and return an aware datetime.

    Naive timestamps are interpreted as Asia/Ho_Chi_Minh.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt


def _canonical_path(value: Any) -> str:
    if value is None:
        return ""
    return PurePosixPath(str(value).replace("\\", "/")).as_posix().lstrip("./")


def _event_timestamp(event: dict[str, Any]) -> datetime | None:
    for key in EVENT_TIME_KEYS:
        dt = parse_timestamp(event.get(key))
        if dt is not None:
            return dt
    return None


def _segment_bounds(segment: dict[str, Any]) -> tuple[datetime, datetime] | None:
    start = parse_timestamp(segment.get("start"))
    end = parse_timestamp(segment.get("end"))
    if start is None or end is None or end <= start:
        return None
    return start, end


def _segment_hints(event: dict[str, Any]) -> set[str]:
    hints: set[str] = set()
    for key in SEGMENT_HINT_KEYS:
        value = event.get(key)
        if not value:
            continue
        path = _canonical_path(value)
        if path:
            hints.add(path)
            hints.add(PurePosixPath(path).name)
    return hints


def _matches_hint(event: dict[str, Any], segment: dict[str, Any]) -> bool:
    hints = _segment_hints(event)
    if not hints:
        return False

    candidates = {
        _canonical_path(segment.get("relative_path")),
        _canonical_path(segment.get("file")),
    }
    candidates.discard("")
    return bool(hints & candidates)


def _prepare_segments(segments: Iterable[dict[str, Any]]):
    ordered = []
    by_hint: dict[str, tuple[dict[str, Any], datetime, datetime]] = {}

    for segment in segments:
        bounds = _segment_bounds(segment)
        if bounds is None:
            continue
        start, end = bounds
        item = (segment, start, end)
        ordered.append(item)

        for value in (
            _canonical_path(segment.get("relative_path")),
            _canonical_path(segment.get("file")),
        ):
            if value:
                by_hint[value] = item
                by_hint[PurePosixPath(value).name] = item

    ordered.sort(key=lambda item: item[1])
    starts = [item[1] for item in ordered]
    return ordered, starts, by_hint


def _resolve_event_prepared(
    event: dict[str, Any],
    ordered: list[tuple[dict[str, Any], datetime, datetime]],
    starts: list[datetime],
    by_hint: dict[str, tuple[dict[str, Any], datetime, datetime]],
) -> dict[str, Any]:
    dt = _event_timestamp(event)
    result = dict(event)
    result["resolved"] = False

    # Event Logger records the canonical MP4 filename. Preserve it as an
    # archive candidate even when the local segment is no longer present.
    segment_hint = event.get("segment")
    if (
        isinstance(segment_hint, str)
        and __import__("re").fullmatch(
            r"cam[12]-\d{8}-\d{6}\.mp4", segment_hint
        )
        and event.get("camera") in ("cam1", "cam2")
        and segment_hint.startswith(event["camera"] + "-")
    ):
        result["archive_candidate"] = segment_hint

    if dt is None:
        result["reason"] = "invalid_event_timestamp"
        return result

    result["timestamp"] = dt.isoformat()

    # A valid canonical segment hint is the fastest path. It is still checked
    # against the event timestamp so stale hints cannot produce false matches.
    hinted = by_hint.get(_canonical_path(segment_hint)) if segment_hint else None
    if hinted is not None:
        segment, start, end = hinted
        if start <= dt < end:
            result["resolved"] = True
            result["segment"] = segment.get("relative_path") or segment.get("file")
            result["offset_seconds"] = round((dt - start).total_seconds(), 3)
            return result

    # Segment starts are sorted, so only the segment immediately preceding the
    # event timestamp can contain it. This replaces an O(events * segments)
    # scan with O(events * log segments).
    index = bisect_right(starts, dt) - 1
    if index >= 0:
        segment, start, end = ordered[index]
        if start <= dt < end:
            result["resolved"] = True
            result["segment"] = segment.get("relative_path") or segment.get("file")
            result["offset_seconds"] = round((dt - start).total_seconds(), 3)
            return result

    result["reason"] = "no_recording_segment"
    return result


def resolve_event(
    event: dict[str, Any],
    segments: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Return a non-destructive normalized event with playback mapping."""
    ordered, starts, by_hint = _prepare_segments(segments)
    return _resolve_event_prepared(event, ordered, starts, by_hint)


def resolve_events(
    events: Iterable[dict[str, Any]],
    segments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve all events without dropping unresolved records."""
    ordered, starts, by_hint = _prepare_segments(segments)
    return [
        _resolve_event_prepared(event, ordered, starts, by_hint)
        for event in events
    ]
