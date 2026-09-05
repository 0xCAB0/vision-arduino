#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-/dev/ttyUSB0}"
FQBN="arduino:avr:uno"
SKETCH="serial_7seg"

echo "==> Compiling $SKETCH"
sudo arduino-cli compile --fqbn "$FQBN" "$SKETCH"

echo "==> Uploading to $PORT"
if id -nG "$USER" | grep -qw dialout; then
    sudo arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$SKETCH"
else
    echo "    (using sg dialout for port access)"
    sudo sg dialout -c "arduino-cli upload -p '$PORT' --fqbn '$FQBN' $SKETCH"
fi

echo "==> Done"
