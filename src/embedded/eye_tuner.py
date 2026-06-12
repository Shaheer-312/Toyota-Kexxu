#!/usr/bin/env python3
"""
Eye Camera Live Tuner — Real-time V4L2 parameter adjustment GUI.

Opens a live preview of the eye camera with interactive sliders for
every relevant V4L2 control. Changes are applied to the hardware
instantly via v4l2-ctl subprocess calls, so you see the effect in
real-time on the video feed.

Usage:
    python3 eye_tuner.py                  # default /dev/eye
    python3 eye_tuner.py /dev/video2      # explicit device

Controls:
    - Adjust any slider to change the camera parameter in real-time.
    - Press 'S' to save the current settings to a file.
    - Press 'R' to reset all controls to factory defaults.
    - Press 'G' to toggle grayscale view (useful for pupil detection).
    - Press 'H' to toggle histogram equalization preview.
    - Press 'Q' or ESC to quit.
"""

import sys
import subprocess
import time
import json
import os
from datetime import datetime

import cv2
import numpy as np

# ─── Configuration ──────────────────────────────────────────────────
DEVICE = sys.argv[1] if len(sys.argv) > 1 else "/dev/eye"
WINDOW_NAME = "Eye Camera Tuner"
SLIDER_WINDOW = "V4L2 Controls"
SLIDER_WIDTH = 700

# Define all tunable controls: (name, v4l2_control_name, min, max, default)
CONTROLS = [
    ("Exposure",      "exposure_time_absolute",    1,    5000,  157),
    ("Gain",          "gain",                      0,    100,   0),
    ("Gamma",         "gamma",                     72,   500,   100),
    ("Brightness",    "brightness",                -64,  64,    0),
    ("Contrast",      "contrast",                  0,    64,    32),
    ("Saturation",    "saturation",                0,    128,   64),
    ("Sharpness",     "sharpness",                 0,    6,     3),
    ("Backlight",     "backlight_compensation",    0,    2,     1),
]

# Recommended values for pupil detection (visible light, dark iris)
RECOMMENDED = {
    "exposure_time_absolute": 300,
    "gain": 15,
    "gamma": 85,
    "brightness": 5,
    "contrast": 45,
    "saturation": 0,
    "sharpness": 4,
    "backlight_compensation": 0,
}


# ─── V4L2 Helpers ───────────────────────────────────────────────────

def v4l2_set(ctrl_name: str, value: int) -> None:
    """Set a V4L2 control on the camera device."""
    subprocess.run(
        ["v4l2-ctl", "-d", DEVICE, "--set-ctrl", f"{ctrl_name}={value}"],
        capture_output=True,
    )


def v4l2_get(ctrl_name: str) -> int | None:
    """Read the current value of a V4L2 control."""
    result = subprocess.run(
        ["v4l2-ctl", "-d", DEVICE, "--get-ctrl", ctrl_name],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        # Output format: "control_name: value"
        try:
            return int(result.stdout.strip().split(":")[-1].strip())
        except (ValueError, IndexError):
            return None
    return None


def v4l2_init() -> None:
    """Set exposure to manual mode and disable dynamic framerate."""
    v4l2_set("auto_exposure", 1)              # 1 = Manual Mode
    v4l2_set("exposure_dynamic_framerate", 0)  # Prevent FPS drops
    v4l2_set("white_balance_automatic", 0)     # Manual white balance


# ─── Slider Callback ────────────────────────────────────────────────

# Global state dictionary tracking current slider values
current_values: dict[str, int] = {}
# Flags for display modes
show_grayscale = False
show_histeq = False


def make_callback(ctrl_name: str):
    """Create a trackbar callback closure for a specific V4L2 control."""
    def callback(value: int):
        # Find the control definition to get the offset
        for _, name, min_val, _, _ in CONTROLS:
            if name == ctrl_name:
                actual_value = value + min_val
                break
        else:
            actual_value = value

        if current_values.get(ctrl_name) != actual_value:
            current_values[ctrl_name] = actual_value
            v4l2_set(ctrl_name, actual_value)
    return callback


def save_settings(filepath: str = "eye_camera_settings.json") -> None:
    """Save current slider values to a JSON file."""
    settings = {
        "device": DEVICE,
        "timestamp": datetime.now().isoformat(),
        "controls": dict(current_values),
    }
    with open(filepath, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"[SAVED] Settings written to {filepath}")


def load_settings(filepath: str = "eye_camera_settings.json") -> dict | None:
    """Load saved settings from a JSON file."""
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        return json.load(f)


# ─── Overlay Drawing ────────────────────────────────────────────────

def draw_info_overlay(frame: np.ndarray, fps: float) -> np.ndarray:
    """Draw a translucent info bar on the top of the frame."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Semi-transparent black bar at top
    cv2.rectangle(overlay, (0, 0), (w, 52), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    # FPS counter
    fps_color = (0, 255, 0) if fps >= 55 else (0, 255, 255) if fps >= 25 else (0, 0, 255)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, fps_color, 1, cv2.LINE_AA)

    # Device path
    cv2.putText(frame, f"Device: {DEVICE}", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    # Mode indicators
    mode_x = w - 250
    if show_grayscale:
        cv2.putText(frame, "[G] GRAY", (mode_x, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    if show_histeq:
        cv2.putText(frame, "[H] HISTEQ", (mode_x, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)

    # Key hints
    cv2.putText(frame, "S:Save  R:Reset  G:Gray  H:HistEQ  P:Preset  Q:Quit", (w // 2 - 220, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA)

    return frame


def draw_histogram(frame: np.ndarray) -> np.ndarray:
    """Draw a small luminance histogram in the bottom-right corner."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.flatten()
    hist = hist / hist.max() * 80  # Normalize to 80px height

    h, w = frame.shape[:2]
    hist_w, hist_h = 256, 80
    x_start = w - hist_w - 10
    y_start = h - hist_h - 10

    # Draw semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (x_start - 5, y_start - 5),
                  (x_start + hist_w + 5, y_start + hist_h + 5), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

    # Draw histogram bars
    for i in range(hist_w):
        bar_height = int(hist[i])
        cv2.line(frame,
                 (x_start + i, y_start + hist_h),
                 (x_start + i, y_start + hist_h - bar_height),
                 (0, 200, 0), 1)

    return frame


def draw_slider_labels() -> None:
    """Draw a labeled canvas into the slider window showing control names and values."""
    row_h = 28
    canvas_h = len(CONTROLS) * row_h + 10
    canvas = np.zeros((canvas_h, SLIDER_WIDTH, 3), dtype=np.uint8)

    for i, (label, ctrl_name, min_val, max_val, _) in enumerate(CONTROLS):
        y = i * row_h + 22
        val = current_values.get(ctrl_name, 0)

        # Control name (left aligned)
        cv2.putText(canvas, f"{label}", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # Current value (center)
        cv2.putText(canvas, f"= {val}", (200, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1, cv2.LINE_AA)

        # Range (right aligned)
        cv2.putText(canvas, f"[{min_val} .. {max_val}]", (300, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1, cv2.LINE_AA)

        # Separator line
        cv2.line(canvas, (0, i * row_h + row_h), (SLIDER_WIDTH, i * row_h + row_h),
                 (40, 40, 40), 1)

    cv2.imshow(SLIDER_WINDOW, canvas)


# ─── Main Loop ──────────────────────────────────────────────────────

def main():
    global show_grayscale, show_histeq

    print(f"[INIT] Opening camera device: {DEVICE}")

    # Initialize camera controls
    v4l2_init()

    # Open video capture
    # Find the /dev/videoN index — if DEVICE is a symlink, resolve it
    device_path = os.path.realpath(DEVICE)
    if device_path.startswith("/dev/video"):
        video_index = int(device_path.replace("/dev/video", ""))
    else:
        print(f"[ERROR] Cannot determine video index from {DEVICE} -> {device_path}")
        sys.exit(1)

    cap = cv2.VideoCapture(video_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[ERROR] Failed to open {DEVICE} (resolved to {device_path})")
        sys.exit(1)

    # Set capture format to MJPEG
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)
    cap.set(cv2.CAP_PROP_FPS, 60)

    print(f"[INIT] Capture opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
          f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ "
          f"{cap.get(cv2.CAP_PROP_FPS):.0f}fps")

    # Create windows — WINDOW_NORMAL allows us to control size
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 800)

    cv2.namedWindow(SLIDER_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(SLIDER_WINDOW, SLIDER_WIDTH, 520)

    # Create sliders for each control
    for label, ctrl_name, min_val, max_val, default in CONTROLS:
        # Read the actual current value from the camera
        actual = v4l2_get(ctrl_name)
        if actual is None:
            actual = default
        current_values[ctrl_name] = actual

        # OpenCV trackbars only support 0-based ranges, so we offset
        slider_range = max_val - min_val
        slider_pos = actual - min_val

        cv2.createTrackbar(
            label,
            SLIDER_WINDOW,
            slider_pos,
            slider_range,
            make_callback(ctrl_name),
        )

    # FPS tracking
    frame_count = 0
    fps = 0.0
    fps_timer = time.monotonic()

    print("[READY] Tuner is running. Press Q or ESC to quit.")
    print("        Press S to save settings, R to reset, G for grayscale, H for histogram EQ.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame grab failed, retrying...")
            time.sleep(0.01)
            continue

        # FPS calculation
        frame_count += 1
        elapsed = time.monotonic() - fps_timer
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            fps_timer = time.monotonic()

        # Apply display modes
        display = frame.copy()

        if show_grayscale:
            gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
            if show_histeq:
                gray = cv2.equalizeHist(gray)
            display = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        elif show_histeq:
            # Apply CLAHE (adaptive histogram equalization) to luminance
            lab = cv2.cvtColor(display, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            display = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

        # Draw overlays
        display = draw_info_overlay(display, fps)
        display = draw_histogram(display)

        cv2.imshow(WINDOW_NAME, display)

        # Update the slider labels canvas with current values
        draw_slider_labels()

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), ord('Q'), 27):  # Q or ESC
            break

        elif key in (ord('s'), ord('S')):
            save_settings()

        elif key in (ord('r'), ord('R')):
            # Reset all controls to defaults
            print("[RESET] Resetting all controls to defaults...")
            for label, ctrl_name, min_val, max_val, default in CONTROLS:
                v4l2_set(ctrl_name, default)
                current_values[ctrl_name] = default
                slider_pos = default - min_val
                cv2.setTrackbarPos(
                    label,
                    SLIDER_WINDOW,
                    slider_pos,
                )
            print("[RESET] Done.")

        elif key in (ord('g'), ord('G')):
            show_grayscale = not show_grayscale
            print(f"[MODE] Grayscale: {'ON' if show_grayscale else 'OFF'}")

        elif key in (ord('h'), ord('H')):
            show_histeq = not show_histeq
            print(f"[MODE] Histogram EQ: {'ON' if show_histeq else 'OFF'}")

        elif key in (ord('p'), ord('P')):
            # Apply recommended pupil detection preset
            print("[PRESET] Applying recommended pupil detection settings...")
            for label, ctrl_name, min_val, max_val, default in CONTROLS:
                if ctrl_name in RECOMMENDED:
                    val = RECOMMENDED[ctrl_name]
                    v4l2_set(ctrl_name, val)
                    current_values[ctrl_name] = val
                    slider_pos = val - min_val
                    cv2.setTrackbarPos(
                        label,
                        SLIDER_WINDOW,
                        slider_pos,
                    )
            print("[PRESET] Applied. Fine-tune from here.")

    cap.release()
    cv2.destroyAllWindows()
    print("[EXIT] Tuner closed.")


if __name__ == "__main__":
    main()
