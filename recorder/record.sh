#!/usr/bin/env bash
set -euo pipefail

: "${TAPO_CAMERA_NAME:?TAPO_CAMERA_NAME is required}"
: "${TAPO_RTSP_URL:?TAPO_RTSP_URL is required}"
: "${TAPO_RECORDINGS_DIR:?TAPO_RECORDINGS_DIR is required}"

mkdir -p "${TAPO_RECORDINGS_DIR}/${TAPO_CAMERA_NAME}"

exec ffmpeg -hide_banner -loglevel warning \
  -rtsp_transport tcp \
  -i "${TAPO_RTSP_URL}" \
  -map 0:v:0 -an \
  -c:v copy \
  -f segment \
  -segment_time "${TAPO_SEGMENT_SECONDS:-300}" \
  -reset_timestamps 1 \
  -strftime 1 \
  "${TAPO_RECORDINGS_DIR}/${TAPO_CAMERA_NAME}/${TAPO_CAMERA_NAME}-%Y%m%d-%H%M%S.mp4"
