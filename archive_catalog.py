#!/usr/bin/env python3
"""Persistent archive catalog for Viewer V2."""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(os.environ.get("TAPO_ROOT", Path(__file__).resolve().parent))
CATALOG_DIR = Path(os.environ.get("TAPO_ARCHIVE_CATALOG_DIR", PROJECT_ROOT / "metadata" / "archive"))
REMOTE_BASE = os.environ.get("TAPO_ARCHIVE_REMOTE_BASE", "tapo-gdrive:Tapo-Archive")
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SEGMENT_RE = re.compile(r"^(cam1|cam2)-(\d{8})-(\d{6})\.mp4$")

def canonical_identity(camera: str, start: str) -> str:
    return f"{camera}/{start}"

def _parse_filename(camera: str, filename: str):
    match = SEGMENT_RE.fullmatch(filename)
    if match is None or match.group(1) != camera:
        return None
    _, ymd, hms = match.groups()
    try:
        dt = datetime.strptime(ymd + hms, "%Y%m%d%H%M%S").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None
    start = dt.isoformat()
    return start, canonical_identity(camera, start)

def _catalog_path(camera: str, date: str) -> Path:
    return CATALOG_DIR / camera / f"{date}.json"

def _read_catalog(camera: str, date: str) -> dict:
    path = _catalog_path(camera, date)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("camera") != camera or data.get("date") != date or not isinstance(data.get("recordings"), list):
            raise ValueError
        return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {"camera": camera, "date": date, "recordings": []}

def _write_catalog(camera: str, date: str, recordings: list[dict]) -> None:
    path = _catalog_path(camera, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"camera": camera, "date": date, "timezone": str(LOCAL_TZ), "version": 1,
            "recordings": sorted(recordings, key=lambda x: (x.get("canonical_start", ""), x.get("archive_path", "")))}
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def _rclone_files(remote: str, *, recursive: bool = False) -> list[str]:
    command = ["rclone", "lsf", "--files-only"]
    if recursive:
        command.insert(2, "-R")
    command.append(remote)
    result = subprocess.run(command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def _date_candidates(remote_base: str, camera: str, date: str) -> list[str]:
    year, month, _ = date.split("-")
    return [
        f"{remote_base.rstrip('/')}/{year}/{month}/{camera}",
        f"{remote_base.rstrip('/')}/{year}/{month}/{date}/{camera}",
    ]

def build_catalog(*, camera: str | None = None, date: str | None = None, remote_base: str = REMOTE_BASE) -> dict:
    cameras = [camera] if camera else ["cam1", "cam2"]
    buckets: dict[tuple[str, str], list[dict]] = {}
    if date:
        sources = [(cam, candidate) for cam in cameras for candidate in _date_candidates(remote_base, cam, date)]
    else:
        sources = [(cam, remote_base) for cam in cameras]
    for source_camera, source in sources:
        for relative in _rclone_files(source, recursive=not date):
            if date:
                prefix = source.removeprefix(remote_base.rstrip("/") + "/").strip("/")
                relative = f"{prefix}/{relative.strip('/')}"
            normalized = relative.strip("/")
            parts = normalized.split("/")
            if not parts:
                continue
            filename = parts[-1]
            parsed_camera = source_camera if filename.startswith(source_camera + "-") else None
            if parsed_camera is None:
                continue
            parsed = _parse_filename(parsed_camera, filename)
            if parsed is None:
                continue
            canonical_start, identity = parsed
            filename_date = canonical_start[:10]
            if date and filename_date != date:
                continue
            key = (parsed_camera, filename_date)
            buckets.setdefault(key, []).append({
                "identity": identity,
                "camera": parsed_camera,
                "canonical_start": canonical_start,
                "archive_path": normalized,
                "filename": filename,
                "archive_base": remote_base,
                "format": "legacy" if len(parts) >= 4 and parts[-3] == filename_date else "v2",
            })
    written = 0
    for (cam, day), recordings in sorted(buckets.items()):
        by_identity = {}
        for item in recordings:
            identity = item["identity"]
            current = by_identity.get(identity)
            if current is None:
                by_identity[identity] = item
                continue
            current_rank = (0 if current.get("format") == "v2" else 1, current.get("archive_path", ""))
            item_rank = (0 if item.get("format") == "v2" else 1, item.get("archive_path", ""))
            if item_rank < current_rank:
                by_identity[identity] = item
        canonical = list(by_identity.values())
        _write_catalog(cam, day, canonical)
        written += len(canonical)
    return {"remote_base": remote_base, "cameras": cameras, "dates": len(buckets), "recordings": written}

def load_catalog(camera: str, date: str) -> dict:
    return _read_catalog(camera, date)

def find_archive_object(camera: str, *, filename: str | None = None, identity: str | None = None, date: str | None = None):
    if camera not in ("cam1", "cam2"):
        return None
    if date is None and filename:
        parsed = _parse_filename(camera, filename)
        if parsed is not None:
            date = parsed[0][:10]
    if date is None and identity:
        date = identity.split("/", 1)[-1][:10]
    if date is None:
        return None
    for item in _read_catalog(camera, date)["recordings"]:
        if filename and item.get("filename") == filename:
            return item
        if identity and item.get("identity") == identity:
            return item
    return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", choices=["cam1", "cam2"])
    parser.add_argument("--date")
    parser.add_argument("--remote", default=REMOTE_BASE)
    args = parser.parse_args()
    print(json.dumps(build_catalog(camera=args.camera, date=args.date, remote_base=args.remote), indent=2))
