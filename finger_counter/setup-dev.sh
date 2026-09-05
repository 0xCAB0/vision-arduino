#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    python3 -m venv --system-site-packages .venv
fi
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt

echo ""
echo "Setup complete. Run the app with:"
echo "  .venv/bin/python finger_counter_app.py"
echo "  .venv/bin/python finger_counter_app.py --selftest"
