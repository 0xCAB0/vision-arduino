# FingerCounter

Desktop app that counts raised fingers from a webcam (MediaPipe Hands, up to 2
hands) and sends the digit (`'0'`–`'5'`) to an Arduino running
`../serial_7seg/serial_7seg.ino` over a serial line at **9600 baud**.

- Counts 0–5 per the 7-segment firmware; **if more than 5 fingers are raised the
  display keeps its last value** (nothing is sent).
- The digit is only sent when it changes, so the serial line stays quiet.
- GUI lets you pick the camera and the Arduino port; a blank Arduino port runs
  the app without serial output.

## NixOS (development)

```bash
nix develop .#vision        # shell with python3 + NIX_LD wheel support
./finger_counter/setup-dev.sh
cd finger_counter
.venv/bin/python finger_counter_app.py
```

The hand-landmark model (`models/hand_landmarker.task`, ~8 MB) is downloaded
automatically on first launch (or by `--selftest`).

`--selftest` checks imports and lists detected cameras / serial ports.

For camera and serial access as a normal user you may need to be in the
`video` and `dialout` groups (`users.users.<you>.extraGroups`).

## Windows (shipping)

1. Install [Python 3.10+](https://python.org) (check "Add to PATH").
2. Double-click `install_windows.bat` (creates `.venv`, installs deps).
3. Double-click `run_windows.bat`.

Build a standalone exe (must be done on a Windows machine — PyInstaller cannot
cross-compile from Linux):

```bat
build_windows.bat
```

Output: `dist\FingerCounter.exe`. Flash the Arduino with
`arduino-cli upload -p COM3 --fqbn arduino:avr:uno serial_7seg` (or the IDE)
beforehand; the app only talks over the COM port.
