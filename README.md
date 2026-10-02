# Home Camera Viewer

A lightweight, self-hosted web viewer for local MP4 camera recordings.

## Scope

This repository is the clean public Viewer V2 distribution. The complete operational NAS repository remains the source of truth for the user's system.

This repository intentionally excludes camera credentials, NAS addresses, production recorder configuration, ONVIF event-logger deployment, backup/retention jobs, real recordings, private archive catalogs, and secrets.

## Features

- daily camera timeline
- recording segment indexing with FFmpeg/ffprobe
- event-to-segment resolution
- HTTP byte-range playback for MP4
- optional archive catalog lookup
- optional on-demand archive restore through rclone
- lightweight browser UI

## Requirements

- Linux
- Python 3.11+
- FFmpeg (ffprobe) for recording indexing
- rclone only when archive fallback is enabled

The viewer core uses Python's standard library; no Python package installation is required for the core viewer.

## Layout

Home-camera/
  viewer/
    viewer.py
    resolver.py
    range_utils.py
    archive.py
    time_utils.py
    index.html
    test_*.py
  recording_indexer.py
  archive_catalog.py
  README.md
  LICENSE

## Expected deployment layout

<project>/
  viewer/
  recordings/
    cam1/
    cam2/
  metadata/
  events/
    cam1-events.jsonl
    cam2-events.jsonl

Configure deployment paths with TAPO_ROOT, TAPO_RECORDINGS_DIR, TAPO_METADATA_DIR, TAPO_EVENTS_DIR, TAPO_ARCHIVE_CATALOG_DIR, TAPO_ARCHIVE_REMOTE_BASE, and TAPO_VIEWER_PORT.

## Run

From the project root, set the deployment paths and run:

    python3 viewer/viewer.py

The default HTTP port is 8080.

Recording filenames are expected in the form cam1-YYYYMMDD-HHMMSS.mp4 or cam2-YYYYMMDD-HHMMSS.mp4.

## Tests

    cd viewer
    python3 -m unittest discover -v

## Archive fallback

Archive fallback is optional. archive_catalog.py builds a local catalog from an rclone remote. viewer/archive.py can restore a missing MP4 into the local recordings tree when requested.

No cloud credentials belong in this repository.

## Design principles

- Keep the viewer lightweight.
- Keep recorder and event-logger responsibilities separate.
- Do not require ONVIF for playback.
- Prefer local recordings.
- Resolve events by timestamp rather than trusting stale segment hints.
- Never guess an unresolved event.
- Use HTTP Range requests so browsers can seek inside MP4 files.
- Keep deployment-specific paths and secrets outside Git.

## License

MIT. See LICENSE.