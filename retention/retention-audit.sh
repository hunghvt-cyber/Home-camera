#!/usr/bin/env bash
set -euo pipefail
ROOT="${TAPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
RECORDINGS="${TAPO_RECORDINGS:-$ROOT/recordings}"
REMOTE="${TAPO_ARCHIVE_REMOTE_BASE:-tapo-gdrive:Tapo-Archive}"
DAYS="${TAPO_RETENTION_DAYS:-7}"
DRY_RUN="${TAPO_RETENTION_DRY_RUN:-1}"
command -v rclone >/dev/null
inventory=$(mktemp); candidates=$(mktemp)
trap 'rm -f "$inventory" "$candidates"' EXIT
rclone lsf -R --files-only --format ps "$REMOTE" > "$inventory"
find "$RECORDINGS" -type f -name '*.mp4' -mtime +"$DAYS" -print > "$candidates"
python3 - "$inventory" "$candidates" <<'PY'
from pathlib import Path
from collections import defaultdict
import os,re,sys
inv,cand=map(Path,sys.argv[1:])
remote=defaultdict(list)
for line in inv.read_text(errors="replace").splitlines():
    if ";" not in line:continue
    p,s=line.rsplit(";",1)
    try:s=int(s)
    except ValueError:continue
    remote[Path(p).name,s].append(p)
safe=[]
for raw in cand.read_text().splitlines():
    p=Path(raw)
    if not re.fullmatch(r"(cam1|cam2)-\d{8}-\d{6}\.mp4",p.name):continue
    hits=remote[p.name,p.stat().st_size]
    if len(hits)==1:safe.append((p,hits[0]))
print(f"RETENTION_CANDIDATES={len(cand.read_text().splitlines())}")
print(f"SAFE_TO_DELETE={len(safe)}")
for p,r in safe:print(f"SAFE\t{p}\t{r}")
if os.environ.get("TAPO_RETENTION_DRY_RUN","1")!="1":
    for p,_ in safe:p.unlink()
PY
