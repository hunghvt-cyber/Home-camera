# Home Camera

A lightweight, self-hosted camera stack for a small NAS: RTSP recording,
optional ONVIF motion events, event-driven cloud archive, local retention, and
the Viewer V2 web UI.

This is the generalized public/rebuildable project. The private
tapo-nas-lab repository remains the source of truth for the current production
NAS deployment.

## Architecture

RTSP camera
  -> recorder/ (FFmpeg, 300-second MP4 segments)
  -> recordings/

ONVIF camera
  -> event-logger/ (optional)
  -> events/*.jsonl
  -> backup/ selects event-backed segments
  -> Google Drive/rclone archive

daily maintenance
  -> backup
  -> retention audit
  -> local 7-day cleanup

Viewer
  -> local recordings first
  -> optional archive catalog/rclone fallback
  -> HTTP Range playback

## Components

- recorder: portable FFmpeg + user-systemd recorder
- event-logger: optional ONVIF Notify -> JSONL logger
- backup: event-driven rclone archive
- retention: conservative local 7-day cleanup
- maintenance: ordered backup/retention orchestration
- viewer: lightweight timeline/event/range-playback web viewer

## Deployment requirements

- Linux
- Python 3.11+
- FFmpeg/ffprobe
- rclone for cloud archive features
- Python packages only for event-logger: aiohttp and onvif-zeep

No production credentials, private IPs, recordings, event logs, archive
catalogs, or rclone configuration belong in Git.

## Repository layout

    recorder/
    event-logger/
    backup/
    retention/
    maintenance/
    viewer/
    recording_indexer.py
    archive_catalog.py
    config/

## Configuration boundary

Use private environment/config files for:

- camera IP/hostname
- camera username/password
- RTSP URL
- ONVIF receiver URL
- local storage paths
- rclone remote name/configuration
- Telegram credentials, if reporting is enabled

Example configuration files are safe templates only.

## Typical setup

1. Clone the repository to the NAS.
2. Configure one recorder environment per camera.
3. Install the user-systemd recorder units and enable Linger.
4. If supported by the camera, configure and test ONVIF Event Logger.
5. Configure rclone and run backup in audit mode.
6. Review retention output before enabling deletion.
7. Enable the daily maintenance timer.
8. Configure Viewer paths and start the Viewer.

Each component has its own README. Production deployments should adapt paths
and service names rather than copying the private NAS configuration verbatim.

## Safety boundaries

- Viewer does not delete recordings.
- Backup does not delete local recordings.
- Retention does not delete cloud archive objects.
- Maintenance runs retention only after backup succeeds.
- Credentials stay outside Git.
- Event Logger is optional and does not own recorder lifecycle.

## Viewer

Viewer V2 supports daily timelines, event-to-segment resolution, local MP4
playback, HTTP byte ranges, and optional archive fallback.

Run:

    python3 viewer/viewer.py

Default port: 8080.

Tests:

    cd viewer
    python3 -m unittest discover -v

## License

MIT. See LICENSE.
