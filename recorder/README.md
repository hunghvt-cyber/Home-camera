# Recorder

A minimal FFmpeg-based recorder for Tapo-compatible RTSP cameras.

## Runtime model

The reference NAS runs the recorder as a per-user systemd service with:

- Restart=always
- RestartSec=5
- user-systemd Linger=yes

The public implementation uses one templated user service per camera:

    tapo-recorder@cam1.service
    tapo-recorder@cam2.service

Each camera gets a private environment file at:

    ~/.config/home-camera/<camera>.env

This keeps RTSP credentials out of Git.

## Storage

The recorder writes 300-second MP4 segments by default:

    recordings/<camera>/<camera>-YYYYMMDD-HHMMSS.mp4

The implementation copies the camera's H.264 video stream without re-encoding.

## Install

From the repository checkout:

    chmod +x recorder/record.sh
    mkdir -p ~/.config/home-camera
    cp recorder/config.example ~/.config/home-camera/cam1.env
    # edit cam1.env with the real camera URL and paths

Install the user unit:

    mkdir -p ~/.config/systemd/user
    cp recorder/systemd/tapo-recorder@.service ~/.config/systemd/user/

Then:

    systemctl --user daemon-reload
    systemctl --user enable --now tapo-recorder@cam1.service

For unattended operation across logout:

    loginctl enable-linger "$USER"

For a second camera, create cam2.env and enable tapo-recorder@cam2.service.

## Notes

- The recorder does not manage retention or backup.
- The recorder does not modify Event Logger state.
- Camera credentials must remain outside the repository.
- Test the RTSP URL manually before enabling the service.
