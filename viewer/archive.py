#!/usr/bin/env python3
"""Safe archive lookup/download for Viewer V2."""
from __future__ import annotations
import os, re, subprocess, tempfile
from pathlib import Path
from archive_catalog import find_archive_object

PROJECT_ROOT = Path(os.environ.get("TAPO_ROOT", Path(__file__).resolve().parent.parent))
RECORDINGS_DIR = Path(os.environ.get("TAPO_RECORDINGS_DIR", PROJECT_ROOT / "recordings"))
SEGMENT_RE = re.compile(r"^(cam1|cam2)-(\d{8})-(\d{6})\.mp4$")

def archive_mapping(camera: str, segment: str):
    if camera not in ("cam1", "cam2") or SEGMENT_RE.fullmatch(segment) is None:
        return None
    item = find_archive_object(camera, filename=segment)
    if item is None:
        return None
    remote_base, archive_path = item.get("archive_base"), item.get("archive_path")
    if not remote_base or not archive_path:
        return None
    return f"{remote_base.rstrip('/')}/{archive_path.lstrip('/')}", RECORDINGS_DIR / camera / segment

def ensure_local_archive(camera: str, segment: str) -> Path:
    mapping = archive_mapping(camera, segment)
    if mapping is None:
        raise FileNotFoundError(f"archive catalog has no object for {camera}/{segment}")
    remote, local_path = mapping
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.is_file() and local_path.stat().st_size > 0:
        return local_path
    fd, tmp_name = tempfile.mkstemp(prefix=f".{local_path.name}.", suffix=".part", dir=str(local_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        result = subprocess.run(["rclone","copyto",remote,str(tmp_path),"--retries","3","--low-level-retries","10"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=900, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"rclone failed with exit {result.returncode}")
        if not tmp_path.is_file() or tmp_path.stat().st_size <= 0:
            raise RuntimeError("archive download produced no MP4")
        os.replace(tmp_path, local_path)
        return local_path
    finally:
        try: tmp_path.unlink()
        except FileNotFoundError: pass
