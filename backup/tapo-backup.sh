#!/usr/bin/env bash
set -euo pipefail
ROOT="${TAPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REMOTE="${TAPO_ARCHIVE_REMOTE_BASE:-tapo-gdrive:Tapo-Archive}"
MIN_AGE="${TAPO_BACKUP_MIN_AGE:-10m}"
WORK=$(mktemp -d /tmp/home-camera-backup.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
command -v rclone >/dev/null
for cam in cam1 cam2; do
  event_file="$ROOT/events/$cam-events.jsonl"
  list="$WORK/$cam.list"
  python3 - "$ROOT" "$event_file" "$list" "$cam" "$MIN_AGE" <<'PY'
from pathlib import Path
import json,re,sys,time
root,event_file,out,cam,age=sys.argv[1:]
mins=int(age[:-1]) if age.endswith("m") else int(age)
cutoff=time.time()-mins*60
keep=set()
p=Path(event_file)
if p.exists():
  for line in p.open(encoding="utf-8"):
    try:r=json.loads(line)
    except json.JSONDecodeError:continue
    s=r.get("segment")
    if s:keep.add(s)
rx=re.compile(rf"^{re.escape(cam)}-\d{{8}}-\d{{6}}\.mp4$")
src=Path(root)/"recordings"/cam
names=[]
for f in src.glob("*.mp4"):
  if rx.fullmatch(f.name) and f.stat().st_mtime<=cutoff and f.name in keep:names.append(f.name)
Path(out).write_text("\n".join(sorted(names))+("\n" if names else ""),encoding="utf-8")
print(f"{cam}: {len(names)} event-backed segments")
PY
  if [ -s "$list" ]; then
    month=$(date -r "$ROOT/recordings/$cam/$(head -n1 "$list")" +%Y/%m)
    timeout --signal=TERM --kill-after=30s "${TAPO_BACKUP_TIMEOUT:-5m}"       rclone copy "$ROOT/recordings/$cam" "$REMOTE/$month/$cam"       --files-from-raw "$list" --ignore-existing --no-traverse       --transfers 2 --checkers 4 --retries 3 --low-level-retries 10
  fi
done
echo "EVENT BACKUP PASS"
