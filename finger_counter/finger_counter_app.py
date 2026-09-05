"""FingerCounter - counts raised fingers from a webcam and sends the digit
to an Arduino running serial_7seg over a serial line at 9600 baud."""

import argparse
import contextlib
import itertools
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import serial
from serial.tools import list_ports

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image, ImageTk

BAUD = 9600
MAX_COUNT = 5
DISPLAY_W = 960
DISPLAY_H = 540
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
ARDUINO_VENDORS = {0x2341, 0x1A86, 0x10C4, 0x2A03, 0x303A}


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


MODEL_PATH = resource_path(os.path.join("models", "hand_landmarker.task"))
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


def count_fingers(landmarks):
    lm = landmarks
    count = 0
    if ((lm[4].x - lm[17].x) ** 2 + (lm[4].y - lm[17].y) ** 2) > (
        (lm[3].x - lm[17].x) ** 2 + (lm[3].y - lm[17].y) ** 2
    ):
        count += 1
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if lm[tip].y < lm[pip].y:
            count += 1
    return count


def draw_hand(frame, landmarks, thickness=2):
    h, w = frame.shape[:2]
    points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, points[a], points[b], (0, 255, 0), thickness, cv2.LINE_AA)
    for p in points:
        cv2.circle(frame, p, thickness + 1, (255, 0, 255), -1, cv2.LINE_AA)


@contextlib.contextmanager
def suppressed_stderr():
    with open(os.devnull, "w") as devnull:
        saved = os.dup(2)
        try:
            sys.stderr.flush()
            os.dup2(devnull.fileno(), 2)
            yield
        finally:
            os.dup2(saved, 2)
            os.close(saved)


def camera_labels():
    try:
        from pygrabber.dshow_graph import FilterGraph
        return {i: name for i, name in enumerate(FilterGraph().get_input_devices())}
    except Exception:
        return {}


def list_cameras(max_index=6):
    found = []
    with suppressed_stderr():
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
            ok = cap.isOpened()
            if ok:
                ok, _ = cap.read()
            cap.release()
            if ok:
                found.append(idx)
    return found


def list_serial_ports():
    ports = []
    for p in list_ports.comports():
        desc = p.description or ""
        if desc.lower() in ("n/a", "unknown"):
            desc = ""
        if p.vid in ARDUINO_VENDORS or "arduino" in desc.lower():
            label = f"Arduino ({p.device})"
        elif desc and desc != p.device:
            label = f"{desc} ({p.device})"
        else:
            label = p.device
        ports.append((label, p.device))
    ports.sort(key=lambda t: (not t[0].startswith("Arduino"), t[1]))
    return ports


def model_present():
    return os.path.isfile(MODEL_PATH)


def permission_hint(exc):
    msg = str(exc)
    if "Permission" not in msg and "Errno 13" not in msg and "Access is denied" not in msg:
        return ""
    return (
        "\n\nPermission denied. Fixes:\n"
        "  Linux: add yourself to the dialout group, then log out/in\n"
        '    NixOS: users.users.<you>.extraGroups = [ "dialout" ];\n'
        "    other distros: sudo usermod -aG dialout $USER\n"
        "  or install the udev rule from 99-arduino.rules (see README)\n"
        "  Windows: close other programs using this COM port"
    )


class CameraIdentifyWindow:
    def __init__(self, root, cam_index):
        self.stop_event = threading.Event()
        self.frame_q = queue.Queue(maxsize=1)
        self._photo = None
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_ANY)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError(f"Cannot open camera {cam_index}")
        self.win = tk.Toplevel(root)
        self.win.title(f"Identify camera {cam_index}")
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        tk.Label(
            self.win,
            text=f"This window shows CAMERA {cam_index}\nClose it when you are done.",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(padx=8, pady=6)
        self.label = tk.Label(self.win, bg="black", width=480, height=360)
        self.label.pack(padx=8, pady=(0, 8))
        self.worker = threading.Thread(target=self._run, args=(cam_index,), daemon=True)
        self.worker.start()
        self._poll()

    def _run(self, cam_index):
        while not self.stop_event.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            h, w = frame.shape[:2]
            cv2.putText(
                frame, f"CAMERA {cam_index}", (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 8, cv2.LINE_AA,
            )
            cv2.putText(
                frame, f"CAMERA {cam_index}", (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3, cv2.LINE_AA,
            )
            scale = min(480 / w, 360 / h)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            try:
                self.frame_q.get_nowait()
            except queue.Empty:
                pass
            self.frame_q.put(frame)

    def _poll(self):
        if self.stop_event.is_set():
            return
        try:
            frame = self.frame_q.get_nowait()
            self._photo = ImageTk.PhotoImage(
                Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                master=self.win,
            )
            self.label.configure(image=self._photo, width=480, height=360)
        except queue.Empty:
            pass
        self.win.after(33, self._poll)

    def close(self):
        self.stop_event.set()
        self.worker.join(timeout=2)
        self.cap.release()
        self.win.destroy()


class FingerCounterApp:
    def __init__(self, root):
        self.root = root
        root.title("FingerCounter -> Arduino serial_7seg")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.frame_q = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.worker = None
        self.cap = None
        self.ser = None
        self.landmarker = None
        self.last_sent = None
        self._photo = None
        self.cam_map = {"Camera index 0": 0}
        self.port_map = {}
        self.identify_win = None

        bar = ttk.Frame(root, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="Camera:").pack(side=tk.LEFT)
        self.cam_var = tk.StringVar(value="Camera index 0")
        self.cam_box = ttk.Combobox(
            bar, textvariable=self.cam_var, values=list(self.cam_map),
            width=26, state="readonly",
        )
        self.cam_box.pack(side=tk.LEFT, padx=(2, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh_cameras).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bar, text="Identify", command=self.identify_camera).pack(
            side=tk.LEFT, padx=(0, 16)
        )

        ttk.Label(bar, text="Arduino:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(bar, textvariable=self.port_var, width=24)
        self.port_box.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(bar, text="Refresh", command=self.refresh_ports).pack(
            side=tk.LEFT, padx=(0, 16)
        )

        ttk.Label(bar, text="Baud: 9600").pack(side=tk.LEFT, padx=(0, 16))
        self.start_btn = ttk.Button(bar, text="Start", command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        self.video = tk.Label(root, bg="black")
        self.video.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        status = ttk.Frame(root, padding=(8, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.count_var = tk.StringVar(value="Fingers: -")
        self.serial_var = tk.StringVar(value="Serial: off")
        self.msg_var = tk.StringVar(value="Select camera and Arduino port, then Start")
        ttk.Label(status, textvariable=self.count_var, font=("TkDefaultFont", 12, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Label(status, textvariable=self.serial_var).pack(side=tk.LEFT, padx=16)
        ttk.Label(status, textvariable=self.msg_var, anchor=tk.E).pack(
            side=tk.RIGHT, fill=tk.X, expand=True
        )

        if not model_present():
            self.msg_var.set(f"Hand model missing: {MODEL_PATH} - run setup first")
        self.refresh_cameras()
        self.refresh_ports()
        root.after(15, self.poll_frames)

    def refresh_cameras(self):
        self.cam_box.configure(values=[])
        threading.Thread(target=self._probe_cameras, daemon=True).start()

    def _probe_cameras(self):
        labels = camera_labels()
        found = list_cameras()
        cam_map = {}
        for idx in found:
            name = labels.get(idx)
            label = f"{name} (index {idx})" if name else f"Camera index {idx}"
            cam_map[label] = idx
        if not cam_map:
            cam_map["Camera index 0 (not detected)"] = 0
        self.root.after(0, lambda: self._cameras_found(cam_map))

    def _cameras_found(self, cam_map):
        self.cam_map = cam_map
        self.cam_box.configure(values=list(cam_map))
        if self.cam_var.get() not in cam_map:
            self.cam_var.set(next(iter(cam_map)))

    def refresh_ports(self):
        ports = list_serial_ports()
        self.port_map = {label: device for label, device in ports}
        self.port_box.configure(values=[label for label, _ in ports])
        arduino = next((label for label, _ in ports if label.startswith("Arduino")), None)
        current = self.port_var.get()
        if current not in self.port_map:
            self.port_var.set(arduino or next(iter(self.port_map), ""))

    def identify_camera(self):
        if self.identify_win is not None:
            self.identify_win.win.lift()
            return
        idx = self.cam_map.get(self.cam_var.get())
        if idx is None:
            messagebox.showerror("FingerCounter", "Select a camera first.")
            return
        try:
            self.identify_win = CameraIdentifyWindow(self.root, idx)
        except RuntimeError as exc:
            messagebox.showerror("FingerCounter", str(exc))
            return
        self.identify_win.win.protocol(
            "WM_DELETE_WINDOW", self._identify_closed
        )

    def _identify_closed(self):
        if self.identify_win is not None:
            self.identify_win.close()
            self.identify_win = None

    def start(self):
        if self.worker is not None:
            return
        if not model_present():
            messagebox.showerror(
                "FingerCounter",
                f"Hand model not found:\n{MODEL_PATH}\n\n"
                "Run setup-dev.sh / install_windows.bat to download it.",
            )
            return
        cam_index = self.cam_map.get(self.cam_var.get())
        if cam_index is None:
            messagebox.showerror("FingerCounter", "Select a valid camera.")
            return
        cap = cv2.VideoCapture(cam_index, cv2.CAP_ANY)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if not cap.isOpened():
            cap.release()
            messagebox.showerror(
                "FingerCounter",
                f"Cannot open camera {cam_index}.\n"
                "On Linux make sure your user is in the 'video' group.",
            )
            return
        ok, _ = cap.read()
        if not ok:
            cap.release()
            messagebox.showerror("FingerCounter", f"Camera {cam_index} returns no frames.")
            return

        ser = None
        label = self.port_var.get().strip()
        port = self.port_map.get(label, label)
        if port:
            try:
                ser = serial.Serial(port, BAUD, timeout=0.1)
            except serial.SerialException as exc:
                cap.release()
                messagebox.showerror(
                    "FingerCounter",
                    f"Cannot open {port}:\n{exc}{permission_hint(exc)}",
                )
                return
            ser.reset_input_buffer()

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = vision.HandLandmarker.create_from_options(options)

        self.cap = cap
        self.ser = ser
        self.landmarker = landmarker
        self.last_sent = None
        self.stop_event.clear()
        self.worker = threading.Thread(
            target=self._run, args=(cap, ser, landmarker), daemon=True
        )
        self.worker.start()
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.serial_var.set(f"Serial: {'on ' + port if ser else 'off (no port)'}")
        self.msg_var.set("Running")

    def stop(self):
        if self.worker is None:
            return
        self.stop_event.set()
        self.worker.join(timeout=3)
        self.worker = None
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.ser is not None:
            self.ser.close()
            self.ser = None
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.count_var.set("Fingers: -")
        self.serial_var.set("Serial: off")
        self.msg_var.set("Stopped")

    def _run(self, cap, ser, landmarker):
        timestamp = itertools.count(start=int(time.time() * 1000), step=33)
        while not self.stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), next(timestamp)
            )
            total = 0
            for hand_landmarks in result.hand_landmarks:
                total += count_fingers(hand_landmarks)
                draw_hand(frame, hand_landmarks)
            self._send(total)
            self._overlay_count(frame, total)
            try:
                self.frame_q.get_nowait()
            except queue.Empty:
                pass
            self.frame_q.put(frame)

    def _overlay_count(self, frame, total):
        cv2.putText(
            frame, str(total), (20, 110), cv2.FONT_HERSHEY_SIMPLEX,
            3.5, (0, 0, 0), 10, cv2.LINE_AA,
        )
        cv2.putText(
            frame, str(total), (20, 110), cv2.FONT_HERSHEY_SIMPLEX,
            3.5, (0, 255, 0), 4, cv2.LINE_AA,
        )

    def _send(self, count):
        if self.ser is None or count == self.last_sent:
            return
        if count > MAX_COUNT:
            self.msg_var.set(f"{count} fingers detected - holding last display value")
            return
        try:
            self.ser.write(str(count).encode("ascii"))
            echo = self.ser.read(64).decode("ascii", errors="replace").strip()
            if echo:
                echo = " | ".join(line for line in echo.splitlines() if line.strip())
                self.msg_var.set(f"Arduino: {echo}")
            self.last_sent = count
        except serial.SerialException as exc:
            self.msg_var.set(f"Serial error: {exc}{permission_hint(exc)}")

    def poll_frames(self):
        try:
            frame = self.frame_q.get_nowait()
            h, w = frame.shape[:2]
            scale = min(DISPLAY_W / w, DISPLAY_H / h)
            nw, nh = int(w * scale), int(h * scale)
            resized = cv2.resize(frame, (nw, nh))
            canvas = Image.new("RGB", (DISPLAY_W, DISPLAY_H), "black")
            canvas.paste(Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)),
                         ((DISPLAY_W - nw) // 2, (DISPLAY_H - nh) // 2))
            self._photo = ImageTk.PhotoImage(canvas, master=self.root)
            self.video.configure(image=self._photo, width=DISPLAY_W, height=DISPLAY_H)
            if self.worker is not None:
                self.count_var.set(
                    f"Fingers: {self.last_sent if self.last_sent is not None else '-'}"
                )
        except queue.Empty:
            pass
        self.root.after(15, self.poll_frames)

    def on_close(self):
        if self.identify_win is not None:
            self.identify_win.close()
            self.identify_win = None
        self.stop()
        self.root.destroy()


def download_model():
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    if model_present():
        return True
    try:
        from urllib.request import urlretrieve
        print(f"Downloading hand model to {MODEL_PATH} ...")
        urlretrieve(MODEL_URL, MODEL_PATH + ".part")
        os.replace(MODEL_PATH + ".part", MODEL_PATH)
        return True
    except OSError as exc:
        print(f"Could not download model: {exc}\nGet it manually from:\n  {MODEL_URL}")
        return False


def selftest():
    print("imports OK: opencv", cv2.__version__, "| mediapipe", mp.__version__,
          "| pyserial", serial.VERSION)
    print("hand model:", "found" if model_present() else "MISSING")
    labels = camera_labels()
    for idx in list_cameras():
        name = labels.get(idx)
        print(f"camera {idx}: {name}" if name else f"camera {idx}")
    for label, device in list_serial_ports():
        print(f"serial: {label} -> {device}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Finger counter -> Arduino serial_7seg")
    parser.add_argument("--selftest", action="store_true", help="check imports and devices")
    args = parser.parse_args()
    if args.selftest:
        download_model()
        sys.exit(selftest())
    if not model_present() and not download_model():
        sys.exit(1)
    root = tk.Tk()
    FingerCounterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
