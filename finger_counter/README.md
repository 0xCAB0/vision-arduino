# FingerCounter

Desktop app that counts raised fingers from a webcam (MediaPipe Hands, up to 2
hands) and sends the digit (`'0'`–`'5'`) to an Arduino running
`../serial_7seg/serial_7seg.ino` over a serial line at **9600 baud**.

- Counts 0–5 per the 7-segment firmware; **if more than 5 fingers are raised the
  display keeps its last value** (nothing is sent).
- The digit is only sent when it changes, so the serial line stays quiet.
- GUI lets you pick the camera and the Arduino port; a blank Arduino port runs
  the app without serial output.
- The live video window shows the result in real time: skeleton overlay on each
  detected hand, the per-hand finger count next to the wrist, a `FINGERS: N`
  caption and a large digit with the total in the bottom-left corner.
- **Identify** button opens a live preview of the selected camera so you can
  tell cameras apart; on Windows, real device names are shown in the dropdown
  (via DirectShow/pygrabber).
- Ports are auto-labelled: boards with Arduino/vendor IDs show as
  `Arduino (COM3)` and are preselected.
- Serial permission problems are detected and reported with the exact fix
  (see below).

### Serial port permission (`could not open device` / permission denied)

Don't run the app as root. Either add yourself to the `dialout` group
(log out/in afterwards):

```nix
# NixOS
users.users.<you>.extraGroups = [ "dialout" "video" ];
```
```bash
# other distros
sudo usermod -aG dialout $USER
```

or paste this into `/etc/nixos/configuration.nix` (NixOS) and run
`sudo nixos-rebuild switch`, then log out/in once:

```nix
users.users.varo.extraGroups = [ "dialout" "video" ];

services.udev.extraRules = ''
  SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", MODE="0666"
  SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666"
  SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0666"
  SUBSYSTEM=="tty", ATTRS{idVendor}=="2a03", MODE="0666"
  SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", MODE="0666"
'';
```

(`dialout` = serial port `/dev/ttyUSB0`, `video` = webcam; the udev rules
additionally grant all users access to Arduino, CH340 and CP210x adapters.)

For camera access you may need the `video` group
(`users.users.<you>.extraGroups = [ "video" ];`).

## NixOS (development)

```bash
nix develop .#vision        # shell with python3 + NIX_LD wheel support
./finger_counter/setup-dev.sh
cd finger_counter
.venv/bin/python finger_counter_app.py
```

The hand-landmark model (`models/hand_landmarker.task`, ~8 MB) is downloaded
automatically on first launch (or by `--selftest`).

`--selftest` checks imports and lists detected cameras (with names) / serial ports.

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
