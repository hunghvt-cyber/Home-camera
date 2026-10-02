#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/home-camera-rebuild.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1" >&2; exit 1; }

command -v python3 >/dev/null || fail "python3 missing"
command -v bash >/dev/null || fail "bash missing"

python3 -m compileall -q "$ROOT" || fail "python compile"
pass "python compile"

if [ "${HOME_CAMERA_INSTALL_DEPS:-0}" = 1 ]; then
  python3 -m venv "$TMP/venv"
  "$TMP/venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$ROOT/event-logger/requirements.txt"
  "$TMP/venv/bin/python" - <<'PY'
import aiohttp
from onvif import ONVIFCamera
print("EVENT_LOGGER_IMPORTS=PASS")
PY
  pass "event-logger dependencies"
fi

while IFS= read -r f; do
  bash -n "$f" || fail "bash syntax: $f"
done < <(find "$ROOT" -type f -name '*.sh' -print)
pass "shell syntax"

(
  cd "$ROOT/viewer"
  python3 -m unittest discover -v
)
pass "viewer unit tests"

# Synthetic backup/retention environment. No production path or remote is touched.
FAKEBIN="$TMP/bin"
TESTROOT="$TMP/root"
mkdir -p "$FAKEBIN" "$TESTROOT/recordings/cam1" "$TESTROOT/recordings/cam2" "$TESTROOT/events" "$TESTROOT/state"

cat > "$FAKEBIN/rclone" <<'RC'
#!/usr/bin/env bash
set -euo pipefail
if [ "$1" = "copy" ]; then
  shift
  list=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--files-from-raw" ]; then
      list="$2"
      shift 2
    else
      shift
    fi
  done
  cat "$list" >> "$MOCK_RCLONE_COPY_LOG"
  exit 0
fi
if [ "$1" = "lsf" ]; then
  cat "$MOCK_RCLONE_LSF"
  exit 0
fi
if [ "$1" = "copyto" ]; then
  exit 1
fi
exit 2
RC
chmod +x "$FAKEBIN/rclone"

OLD1="$TESTROOT/recordings/cam1/cam1-20261001-000000.mp4"
OLD2="$TESTROOT/recordings/cam1/cam1-20261001-000500.mp4"
OLD3="$TESTROOT/recordings/cam1/cam1-20261001-001000.mp4"
printf 'aaaa' > "$OLD1"
printf 'bbbb' > "$OLD2"
printf 'cccc' > "$OLD3"
touch -d '8 days ago' "$OLD1" "$OLD2" "$OLD3"

cat > "$TESTROOT/events/cam1-events.jsonl" <<EOF
{"camera":"cam1","type":"motion","event_local":"2026-10-01T00:01:00+07:00","segment":"cam1-20261001-000000.mp4"}
EOF

export PATH="$FAKEBIN:$PATH"
export MOCK_RCLONE_COPY_LOG="$TMP/copy.log"
: > "$MOCK_RCLONE_COPY_LOG"

TAPO_ROOT="$TESTROOT" TAPO_ARCHIVE_REMOTE_BASE="mock:Tapo-Archive" TAPO_BACKUP_MIN_AGE=10m \
  "$ROOT/backup/tapo-backup.sh" > "$TMP/backup.out"

grep -qx 'cam1-20261001-000000.mp4' "$MOCK_RCLONE_COPY_LOG" || fail "event-backed segment not selected"
if grep -qx 'cam1-20261001-001000.mp4' "$MOCK_RCLONE_COPY_LOG"; then
  fail "unrelated segment selected"
fi
pass "backup event selection"

printf 'cam1-20261001-000000.mp4;4\n' > "$TMP/remote.txt"
printf 'cam1-20261001-000500.mp4;4\n' >> "$TMP/remote.txt"
export MOCK_RCLONE_LSF="$TMP/remote.txt"

TAPO_ROOT="$TESTROOT" TAPO_ARCHIVE_REMOTE_BASE="mock:Tapo-Archive" TAPO_RETENTION_DAYS=7 TAPO_RETENTION_DRY_RUN=1 \
  "$ROOT/retention/retention-audit.sh" > "$TMP/retention.out"

grep -q '^SAFE_TO_DELETE=2$' "$TMP/retention.out" || fail "retention safe-set mismatch"
[ -f "$OLD1" ] && [ -f "$OLD2" ] || fail "dry-run deleted a file"
pass "retention dry-run safety"

TAPO_ROOT="$TESTROOT" TAPO_ARCHIVE_REMOTE_BASE="mock:Tapo-Archive" TAPO_RETENTION_DAYS=7 TAPO_RETENTION_DRY_RUN=0 \
  "$ROOT/retention/retention-audit.sh" > "$TMP/retention-apply.out"

[ ! -f "$OLD1" ] && [ ! -f "$OLD2" ] || fail "retention apply did not delete safe files"
[ -f "$OLD3" ] || fail "retention deleted unmatched file"
pass "retention apply safety"

cat > "$TMP/backup-pass.sh" <<'EOF'
#!/usr/bin/env bash
echo BACKUP_OK
EOF
chmod +x "$TMP/backup-pass.sh"

cat > "$TMP/maintenance.conf" <<EOF
BACKUP_COMMAND="$TMP/backup-pass.sh"
TAPO_ARCHIVE_REMOTE_BASE="mock:Tapo-Archive"
TAPO_RECORDINGS="$TESTROOT/recordings"
TAPO_RETENTION_DAYS=7
TAPO_MAINTENANCE_APPLY=0
EOF

TAPO_ROOT="$TESTROOT" TAPO_MAINTENANCE_CONF="$TMP/maintenance.conf" \
  "$ROOT/maintenance/daily-maintenance.sh" > "$TMP/maintenance.out"

grep -q '^STATUS=PASS$' "$TESTROOT/state/daily-maintenance/latest.env" || fail "maintenance status"
grep -q '^BACKUP=PASS$' "$TESTROOT/state/daily-maintenance/latest.env" || fail "maintenance backup"
grep -q '^RETENTION=DRY_RUN$' "$TESTROOT/state/daily-maintenance/latest.env" || fail "maintenance retention"
pass "maintenance orchestration"

echo "REBUILD_ZERO_TEST=PASS"
