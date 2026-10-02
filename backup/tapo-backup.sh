#!/usr/bin/env bash
set -euo pipefail
ROOT="${TAPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REMOTE="${TAPO_ARCHIVE_REMOTE_BASE:-tapo-gdrive:Tapo-Archive}"
MIN_AGE="${TAPO_BACKUP_MIN_AGE:-10m}"
FULL_DATES="${TAPO_ARCHIVE_FULL_DATES:-}"
WORK=$(mktemp -d /tmp/home-camera-backup.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
command -v rclone >/dev/null

for cam in cam1 cam2; do
  event_file="$ROOT/events/$cam-events.jsonl"
  python3 - "$ROOT" "$event_file" "$WORK" "$cam" "$MIN_AGE" "$FULL_DATES" <<'PY'
from pathlib import Path
import json,re,sys,time
root,event_file,work,cam,age,full_dates=sys.argv[1:]
mins=int(age[:-1]) if age.endswith("m") else int(age)
cutoff=time.time()-mins*60
full={x.strip() for x in full_dates.split(",") if x.strip()}
keep_by_date={}
p=Path(event_file)
if p.exists():
  for line in p.open(encoding="utf-8"):
    try:r=json.loads(line)
    except json.JSONDecodeError:continue
    date=str(r.get("event_local",""))[:10]; seg=r.get("segment")
    if date and seg:keep_by_date.setdefault(date,set()).add(seg)
rx=re.compile(rf"^{re.escape(cam)}-(\d{{8}})-(\d{{6}})\.mp4$")
src=Path(root)/"recordings"/cam
groups={}
for f in src.glob("*.mp4"):
  m=rx.fullmatch(f.name)
  if not m or f.stat().st_mtime>cutoff: continue
  date=f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:]}"
  if date in full or f.name in keep_by_date.get(date,set()):
    groups.setdefault(date[:7],[]).append(f.name)
for ym,names in groups.items():
  out=Path(work)/f"{cam}-{ym.replace('-','')}.list"
  out.write_text("\n".join(sorted(names))+"\n",encoding="utf-8")
  print(f"{cam} {ym}: {len(names)} selected segments")
PY

  for list in "$WORK/$cam-"*.list; do
    [ -f "$list" ] || continue
    ym=$(basename "$list" .list | cut -d- -f2)
    year=${ym:0:4}; month=${ym:4:2}
    timeout --signal=TERM --kill-after=30s "${TAPO_BACKUP_TIMEOUT:-5m}" \
      rclone copy "$ROOT/recordings/$cam" "$REMOTE/$year/$month/$cam" \
      --files-from-raw "$list" --ignore-existing --no-traverse \
      --transfers 2 --checkers 4 --retries 3 --low-level-retries 10
  done
done
echo "EVENT BACKUP PASS"
