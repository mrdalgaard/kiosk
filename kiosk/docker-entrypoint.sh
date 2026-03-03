#!/bin/sh
set -e

# Ensure the appuser owns the mounted volume directory (fallback handles missing dir)
mkdir -p /app/kiosk/static/images
chown -R appuser:appuser /app/kiosk/static/images

# Execute the passed command (CMD) from Dockerfile, dropping root privileges
exec su-exec appuser "$@"
