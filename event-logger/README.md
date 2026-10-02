# Event Logger

Optional ONVIF motion-event ingestion. It accepts Notify messages, keeps only
Changed + IsMotion=true events, and appends JSONL records using an explicit
local timezone.

Install Python dependencies from requirements.txt, then place camera-specific
credentials and paths in a private user environment file.

This component is optional and firmware-dependent. It does not own recording,
backup, retention, or Viewer state.
