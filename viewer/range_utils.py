"""HTTP byte-range parsing helpers for MP4 playback.

Only single byte ranges are supported. Invalid or unsatisfiable ranges return None.
"""

from __future__ import annotations


def parse_range(value: str | None, size: int) -> tuple[int, int] | None:
    """Return inclusive (start, end) byte offsets for one Range header."""
    if not value or size <= 0 or not value.startswith("bytes="):
        return None

    spec = value[6:].strip()
    if not spec or "," in spec:
        return None

    start_text, sep, end_text = spec.partition("-")
    if not sep:
        return None

    try:
        if start_text:
            start = int(start_text)
            if start < 0 or start >= size:
                return None
            end = int(end_text) if end_text else size - 1
            if end < start:
                return None
            return start, min(end, size - 1)

        # Suffix range: bytes=-N
        suffix = int(end_text)
        if suffix <= 0:
            return None
        length = min(suffix, size)
        return size - length, size - 1
    except ValueError:
        return None
