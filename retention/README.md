# Retention

Default local retention is 7 days. A recording is eligible only when it is
older than the retention window and has a unique remote match by filename and
exact size.

The default is dry-run. Set TAPO_RETENTION_DRY_RUN=0 only after reviewing the
audit output. This layer never deletes archive objects.
