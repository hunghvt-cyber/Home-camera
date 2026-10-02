# Backup

The reference design uses rclone with Google Drive as the archive backend.

Only event-backed recording segments are selected for archive. The Viewer and
retention layers never write archive data.

Configure the remote outside Git:

    TAPO_ARCHIVE_REMOTE_BASE=tapo-gdrive:Tapo-Archive

A deployment may add a periodic full remote inventory/reconciliation pass.
