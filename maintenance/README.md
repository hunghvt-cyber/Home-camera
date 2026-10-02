# Daily Maintenance

The maintenance layer is intentionally an orchestrator, not another copy of
the backup algorithm.

Order:

1. run the configured backup command;
2. only after backup succeeds, run retention;
3. write a small status file;
4. optionally publish the status through a deployment-specific reporting job.

Use TAPO_MAINTENANCE_APPLY=0 for audit/dry-run mode.
