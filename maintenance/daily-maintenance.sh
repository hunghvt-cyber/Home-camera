#!/usr/bin/env bash
set -euo pipefail
ROOT="${TAPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
STATE="${TAPO_STATE_DIR:-$ROOT/state/daily-maintenance}"
CONF="${TAPO_MAINTENANCE_CONF:-$ROOT/config/daily-maintenance.conf}"
mkdir -p "$STATE"
[ -f "$CONF" ] && . "$CONF"
APPLY="${TAPO_MAINTENANCE_APPLY:-0}"
exec 9>"$STATE/maintenance.lock"; flock -n 9 || exit 2
status=PASS; backup=SKIPPED; retention=SKIPPED
if [ -n "${BACKUP_COMMAND:-}" ]; then
  if bash -c "$BACKUP_COMMAND"; then backup=PASS; else backup=FAIL; status=FAIL; fi
else backup=FAIL; status=FAIL; fi
if [ "$backup" = PASS ]; then
  if [ "$APPLY" = 1 ]; then
    TAPO_RETENTION_DRY_RUN=0 "$ROOT/retention/retention-audit.sh" && retention=PASS || { retention=FAIL; status=FAIL; }
  else
    TAPO_RETENTION_DRY_RUN=1 "$ROOT/retention/retention-audit.sh" && retention=DRY_RUN || { retention=FAIL; status=FAIL; }
  fi
fi
cat > "$STATE/latest.env" <<EOF
LAST_UPDATE=$(date -Is)
STATUS=$status
BACKUP=$backup
RETENTION=$retention
EOF
cat "$STATE/latest.env"
[ "$status" = PASS ]
