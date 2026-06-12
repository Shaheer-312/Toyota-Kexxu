<br># Toyota-Kexxu — Wearable Eye-Tracking System for Vehicle Inspection QA

<div align="center">
  <img src="docs/hardware/assets/system_overview.png" alt="System Overview" width="720"/>
  <br/>
  <strong>A dual-prototype, open-architecture wearable eye-tracking platform for Toyota Quality Assurance inspection workflows</strong>
  <br/><br/>
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-C51A4A?logo=raspberrypi&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Interface-V4L2%20%7C%20libcamera-brightgreen" />
  <img src="https://img.shields.io/badge/Status-Active%20Development-orange" />
</div>

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Hardware Prototypes](#hardware-prototypes)
- [Software Stack](#software-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Data Pipeline](#data-pipeline)
- [Team](#team)

---

## Overview

Toyota vehicle inspection officers conduct **~150 engine inspections per day**, recording defects manually on paper checksheets with no objective verification that the inspector actually looked at each required component.

This project builds an end-to-end wearable eye-tracking system to modernize this process. An inspector wears a lightweight dual-camera glasses unit while walking through an inspection. Their gaze is captured, processed, and mapped onto the scene — generating heatmaps and session reports that confirm which components were visually inspected and for how long.

**Two hardware prototypes are developed in parallel:**

| Prototype | Camera Interface | Eye Camera | Scene Camera |
|---|---|---|---|
| **Kexxu (Industry-Provided)** | USB 3.0 UVC | 1280×800 @ 60fps MJPEG | 1280×720 @ 30fps MJPEG |
| **Custom (This Project)** | MIPI CSI-2 (native RPi 5) | OV9281 Global Shutter @ 60fps | RPi Camera Module 3 NoIR @ 30fps |

Both prototypes run on a **Raspberry Pi 5 (8GB)** and share the same software architecture.

---

## System Architecture

```
                HEAD UNIT (Glasses)
        ┌──────────────────────────────┐
        │  Eye Camera   │  Scene Camera │
        │  (60 fps)     │  (30 fps)     │
        │  IR LEDs (850nm illumination) │
        └────────────┬─────────────────┘
                     │ USB 3.0 / CSI-2 cable loom
                     ▼
        ┌─────────────────────────────────────┐
        │         WAIST CASE (Belt/Pocket)     │
        │  Raspberry Pi 5 (BCM2712, 8GB RAM)  │
        │  ├── Capture Pipeline (V4L2/CSI)    │
        │  ├── FastAPI Web Dashboard           │
        │  └── NVMe SSD (session storage)     │
        └────────────┬────────────────────────┘
                     │ WiFi / USB upload
                     ▼
        ┌─────────────────────────────────────┐
        │         CLOUD PROCESSING            │
        │  Docker + GPU (Vast.ai / GCP)       │
        │  ├── Pupil Detection (PuRe / CNN)   │
        │  ├── Gaze Estimation (Homography)   │
        │  └── Heatmap Generation (KDE)       │
        └─────────────────────────────────────┘
```

**Design Philosophy — Decoupled Architecture:**
The glasses unit houses *only* cameras and IR LEDs. All compute, power, and storage are offloaded to the waist case. This follows industry precedent set by Tobii Pro Glasses 3 (76.5g head unit, 312g recorder) and Pupil Labs Invisible, and eliminates the >2mm slippage caused by heavy head units that invalidates angular calibration.

---

## Hardware Prototypes

### Kexxu Prototype (Industry-Provided Baseline)
| Property | Eye Camera | Scene Camera |
|---|---|---|
| USB VID:PID | `0c45:6366` (Microdia/Sonix) | `0bda:5842` (Realtek) |
| Persistent Device | `/dev/eye` | `/dev/front` |
| Resolution | 1280×800 | 1280×720 |
| Target FPS | 60 fps | 30 fps |
| Format | MJPEG | MJPEG |

> **Note:** Both Kexxu cameras connect via USB 2.0. Persistent device symlinks (`/dev/eye`, `/dev/front`) are assigned using custom `udev` rules found in `config/99-kexxu-cameras.rules`.

### Custom Prototype (This Project)
| Component | Part | Spec |
|---|---|---|
| Compute | Raspberry Pi 5 (SC1112) | BCM2712, Quad Cortex-A76 @ 2.4GHz, 8GB LPDDR4X |
| Eye Camera | ArduCam OV9281 NoIR | 1MP, Global Shutter, MIPI CSI-2, IR-sensitive |
| Scene Camera | RPi Camera Module 3 NoIR | 12MP, MIPI CSI-2, wide-angle, IR-sensitive |
| Storage | NVMe SSD (via M.2 HAT+) | PCIe 2.0 x1, 256GB+ |
| IR Illumination | 850nm LEDs × 4/eye | GPIO-driven via transistor circuit, 30–50mA |
| Frame | 3D Printed (PETG) | Fusion 360 CAD, clips over safety glasses |

---

## Software Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Camera Capture** | `linuxpy` (V4L2) / `Picamera2` (libcamera) | USB (Kexxu) and CSI (custom) camera streaming |
| **Synchronization** | `multiprocessing.Event` + `CLOCK_MONOTONIC` | Nanosecond-precise inter-camera timestamp alignment |
| **Storage** | MKV container + CSV timestamps | Fault-tolerant MJPEG stream + frame metadata |
| **Web Dashboard** | FastAPI + HTMX + Chart.js | Session management, live FPS monitoring, results UI |
| **Pupil Detection** | PuRe (CV) + YOLOv8-nano (ML fallback) | High-speed pupil ellipse detection on captured frames |
| **Gaze Estimation** | `cv2.findHomography` + geometric model | 3D gaze vector estimation from 9-point calibration |
| **Heatmap** | SciPy KDE + OpenCV | Gaussian density overlay mapped to scene camera view |
| **Cloud Processing** | Docker + Vast.ai / GCP | GPU-accelerated offline ML inference |

---

## Repository Structure

```
toyota-kexxu-eyetracking/
├── config/                     # System-level configs (udev, systemd)
│   ├── 99-kexxu-cameras.rules  # Persistent USB camera symlinks
│   └── kexxu-dashboard.service # systemd auto-start service
├── data/                       # Local session data — GIT IGNORED
│   └── README.md
├── docs/
│   ├── hardware/               # CAD files (STEP/STL), BOM, schematics
│   ├── setup/                  # Environment setup SOPs
│   └── verification/           # Test plans, jitter reports, accuracy logs
├── src/
│   ├── embedded/               # RPi 5 dual-camera capture pipeline
│   │   ├── capture_pipeline.py
│   │   ├── camera_backends.py  # CSI / USB abstraction layer
│   │   └── utils.py
│   ├── dashboard/              # FastAPI web dashboard
│   │   ├── static/
│   │   ├── templates/
│   │   └── main.py
│   └── post_processing/        # Offline CV/ML analysis
│       ├── pupil_detection.py
│       ├── gaze_estimation.py
│       └── heatmap_gen.py
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Getting Started

### Prerequisites
- Raspberry Pi 5 (8GB) running **Raspberry Pi OS Bookworm** (64-bit)
- Official 27W USB-C Power Supply
- Python 3.11+

### 1. Clone the Repository
```bash
git clone https://github.com/<your-org>/toyota-kexxu-eyetracking.git
cd toyota-kexxu-eyetracking
```

### 2. Set Up Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Install System Dependencies
```bash
sudo apt update && sudo apt install -y \
    v4l-utils libcamera-apps python3-picamera2 ffmpeg
```

### 4. Register Camera udev Rules (Kexxu Prototype)
This assigns persistent symlinks `/dev/eye` and `/dev/front` based on USB serial numbers, so device paths never change.
```bash
sudo cp config/99-kexxu-cameras.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -l /dev/eye /dev/front   # Verify symlinks
```

### 5. Lock Camera Exposure (Kexxu Prototype)
Auto-exposure causes dynamic framerate reduction. Lock it to a fixed value before running.
```bash
# Eye camera — lock exposure at 15.7ms (enables stable 60fps)
v4l2-ctl -d /dev/eye --set-ctrl=auto_exposure=1
v4l2-ctl -d /dev/eye --set-ctrl=exposure_time_absolute=157
v4l2-ctl -d /dev/eye --set-ctrl=exposure_dynamic_framerate=0

# Scene camera — lock exposure
v4l2-ctl -d /dev/front --set-ctrl=auto_exposure=1
v4l2-ctl -d /dev/front --set-ctrl=exposure_time_absolute=166
```

### 6. Run a Capture Session
```bash
python3 src/embedded/capture_pipeline.py
# Enter a session name when prompted (e.g., corolla_inspection_01)
# Press Ctrl+C to stop recording cleanly
```

**Session output** is written to `data/<session_name>/`:
```
data/corolla_inspection_01/
├── eye.mkv              # Raw MJPEG eye stream
├── front.mkv            # Raw MJPEG scene stream
├── eye_timestamps.csv   # [frame_index, timestamp_ns]
├── front_timestamps.csv # [frame_index, timestamp_ns]
└── session_meta.csv     # [camera, start_ns, end_ns, total_frames]
```

---

## Data Pipeline

```
  [Capture on RPi 5]                [Upload]             [Cloud Processing]
  eye.mkv + front.mkv  ──── WiFi/USB ────►  Vast.ai GPU Container
  eye_timestamps.csv                         ├── Pupil Detection (PuRe/YOLO)
  front_timestamps.csv                       ├── Gaze Vector Estimation
                                             ├── Temporal Alignment (CSV join)
                                             └── Heatmap Generation (KDE)
                                                          │
                                                          ▼
                                               [Dashboard Results]
                                               Inspection heatmap + gaze trace
                                               mapped to Toyota Engine IIL checklist
```

**Why MJPEG?** Each frame is an independent JPEG — no inter-frame dependencies. This enables instant frame-accurate seeking during CV analysis, no artifact propagation from corrupted keyframes (unlike H.264), and zero CPU overhead on the RPi 5 since compression happens in the camera hardware.

---

## Team

| Member | Role |
|---|---|
| **Shaheer** | Embedded Systems Lead — Capture pipeline, V4L2/libcamera, RPi 5 system architecture |
| **Basil Elahi Shamsi** | CV/ML Lead — Pupil detection, gaze estimation, cloud pipeline (Docker/Vast.ai) |
| **Wasiq** | Software/Dashboard Lead — FastAPI backend, Web UI, Toyota checklist digitization |
| **Hunain Raza** | Hardware/CAD Lead — 3D frame design (Fusion 360), IR LED circuitry, camera selection |
| **Shem Ezekiel Anthony** | Verification Lead — Test plans, jitter analysis, calibration accuracy benchmarks |

---

## Research Context

This system is designed to study two core research questions:
1. **Does 60fps eye tracking measurably improve gaze detection accuracy over 30fps** during rapid saccadic movements in vehicle inspection scenarios?
2. **Is a `CLOCK_MONOTONIC` software timestamp sufficient** (sub-16ms jitter) to temporally align the eye and scene camera streams for gaze-to-world projection?

Key academic references:
- Niehorster et al. (2020) — Slippage impact on wearable eye-tracker calibration
- Santini et al. (2018) — *PuRe: Robust pupil detection for real-time pervasive eye tracking*
- Raj et al. (2023) — Embedded real-time eye-tracking pipeline at 30fps+

---

<div align="center">
  Final Year Project — University of Engineering & Technology<br/>
  Industry Partner: Toyota Indus Motor Company (TMC Pakistan)
</div>
