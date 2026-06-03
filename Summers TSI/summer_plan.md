# Toyota-Kexxu — 10-Week Summer Plan

**Team:** 5 members | **Platform:** Raspberry Pi 5 | **Start:** June 2026

---

## Master Learning Map

### L1. USB 3.0 Protocol & Camera Interfaces

**What to learn:**
- USB transfer types: **Isochronous** (guaranteed bandwidth, used by cameras), Bulk (storage), Interrupt (input devices)
- Bandwidth: USB 3.0 = 5Gbps theoretical, ~400MB/s sustained. USB 2.0 = 480Mbps, ~35MB/s sustained
- The **80% rule**: only 80% of USB bandwidth can be reserved for isochronous (camera) transfers
- UVC (USB Video Class): standardized camera protocol — plug-and-play on Linux via `uvcvideo` kernel driver
- Bandwidth is per **host controller**, not per port. RPi 5 has **2 independent xHCI controllers** (one per diagonal port pair)

**Ideal interface for YOUR case:**
| Interface | Bandwidth | Latency | RPi 5 Support | Verdict |
|---|---|---|---|---|
| **MIPI CSI-2** | 1.5Gbps/lane × 4 lanes | Lowest (DMA) | ✅ 2 ports, 22-pin | **Best for custom prototype** |
| USB 3.0 UVC | 5Gbps shared | Medium | ✅ 2 ports | Good for Kexxu prototype |
| USB 2.0 UVC | 480Mbps shared | Medium | ✅ 2 ports | Current Kexxu setup |

**Recommendation:** Use **CSI cameras for your custom prototype** (zero-copy DMA, lowest latency, no USB bandwidth issues). Keep USB UVC for Kexxu compatibility.

**Where to learn:**
- USB spec summary: [USB in a NutShell](https://www.beyondlogic.org/usbnutshell/)
- V4L2 API: [kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html)
- RPi CSI: [raspberrypi.com/documentation/computers/camera_software.html](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- `libcamera` docs: [libcamera.org](https://libcamera.org/)
- Run `lsusb -t` to see your USB topology and controller assignment

---

### L2. Data Formats

| Format | Compression | Frame Independence | Seekability | Storage (30min) | Best For |
|---|---|---|---|---|---|
| **MJPEG** | ~10:1 | ✅ Every frame standalone | ✅ Instant | ~9.7 GB | Capture & analysis |
| **H.264** | ~50:1 | ❌ GOP-dependent | ⚠️ Needs keyframes | ~2 GB | Long-term storage |
| H.265 | ~70:1 | ❌ GOP-dependent | ⚠️ Expensive decode | ~1.5 GB | 4K+ only |
| Raw/YUYV | None | ✅ | ✅ | ~108 GB | Ground truth only |

**Recommendation for your project:**
- **Capture in MJPEG** (camera does compression, zero CPU cost, frame-independent = perfect for CV analysis)
- **Archive in H.264** with short GOP (keyframe every 1s) for long-term storage
- **Metadata in CSV** (simple, universal, fast writes) — your current `frame_index, timestamp_ns` format is correct
- Container: Use **MKV** (Matroska) — supports MJPEG natively, fault-tolerant (recoverable on crash)

**Where to learn:**
- FFmpeg wiki: [trac.ffmpeg.org/wiki](https://trac.ffmpeg.org/wiki)
- Video container formats: search "Matroska vs AVI vs MP4 for scientific data"
- Practice: `ffprobe`, `ffmpeg` CLI tools for inspecting and converting

---

### L3. Computer Vision vs Machine Learning for Pupil Detection

| Approach | Method | FPS on RPi 5 | Accuracy | Setup Effort |
|---|---|---|---|---|
| **CV (Traditional)** | PuRe/PuReST ellipse fitting | ~60-120fps | Good (controlled IR) | Low — tune params |
| **CV (Traditional)** | Blob detection + Hough circles | ~100+fps | Moderate | Lowest |
| **ML (Lightweight)** | YOLOv8-nano pupil detector | ~30-45fps | Good | Medium — need training data |
| **ML (Deep)** | CNN gaze estimation (ResNet) | ~10-15fps | Best | High — GPU recommended |
| **Hybrid** | PuRe detection + Kalman tracking | ~60fps | Very good | Medium |

**Recommendation:** Start with **PuRe (CV)** for IR-illuminated eye images. It's fast, no training data needed, and proven for embedded. Add **lightweight ML** (YOLOv8-nano) as a fallback for difficult frames. This hybrid approach is the 2025 industry trend.

**Where to learn:**
- PuRe paper: Santini et al., "PuRe: Robust pupil detection for real-time pervasive eye tracking" (2018)
- OpenCV tutorials: [docs.opencv.org/4.x/d6/d00/tutorial_py_root.html](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- MediaPipe face/iris: [mediapipe.readthedocs.io](https://mediapipe.readthedocs.io/)
- Pupil Labs open-source: [github.com/pupil-labs/pupil](https://github.com/pupil-labs/pupil)
- EyeTrackVR community: [github.com/EyeTrackVR/EyeTrackVR](https://github.com/EyeTrackVR/EyeTrackVR)
- gazeMapper (wearable gaze→world mapping): [github.com/dcnieho/gazeMapper](https://github.com/dcnieho/gazeMapper)

---

### L4. Cloud Post-Processing

| Provider | GPU Cost/hr | Student Credits | Best For |
|---|---|---|---|
| **Google Cloud (GCP)** | $0.35-2.48 (T4-A100) | $300 free + research grants | ML training, Vertex AI |
| AWS | $0.53-3.06 (T4-A100) | $100-300 + research credits | Broadest services |
| Azure | $0.90-3.06 | $100 student + GitHub Student | MS ecosystem |
| **Vast.ai** | $0.10-0.50 (community GPUs) | N/A (pay-as-you-go) | **Cheapest for batch jobs** |
| **RunPod** | $0.20-0.75 | N/A | Easy Docker GPU containers |
| Google Colab Pro | $10/month flat | Free tier available | Quick experiments |

**Recommendation:** Use **Google Colab** for learning/prototyping (free T4 GPU). Use **Vast.ai or RunPod** for batch processing recorded sessions (cheapest GPU hours). Apply for **GCP Research Credits** if your university supports it.

**Architecture:** RPi 5 captures data locally → upload sessions via WiFi/USB to cloud → cloud runs heavy ML inference → results download as CSVs/heatmaps

**VM vs Container:** Use **Docker containers** on cloud GPU instances — reproducible, portable, no OS setup. Pre-build a container with OpenCV + PyTorch + your pipeline code.

**Where to learn:**
- Docker basics: [docs.docker.com/get-started](https://docs.docker.com/get-started/)
- Google Colab: [colab.research.google.com](https://colab.research.google.com/)
- Vast.ai: [vast.ai](https://vast.ai/)

---

### L5. Hardware & 3D Modeling

**Camera selection for custom prototype:**

| Camera | Interface | Resolution | Shutter | IR Sensitive | Price | Notes |
|---|---|---|---|---|---|---|
| **RPi Global Shutter Camera** | CSI | 1.6MP | Global ✅ | Check NoIR variant | ~$50 | Official, best motion capture |
| **Innomaker OV7251** | CSI | VGA (640×480) | Global ✅ | ✅ Mono IR | ~$25 | Popular in DIY eye tracking |
| **ArduCam OV9281** | CSI | 1MP | Global ✅ | ✅ NoIR available | ~$30 | Good balance |
| RPi Camera Module 3 NoIR | CSI | 12MP | Rolling | ✅ NoIR | ~$35 | High-res but rolling shutter |

**Recommendation:** Use **Innomaker OV7251 or ArduCam OV9281** (global shutter + IR sensitive) for the eye camera via CSI. Use **RPi Camera Module 3** for the front/scene camera via second CSI port. Both connect directly to RPi 5's dual CSI ports — zero USB bandwidth issues.

**3D printing workflow:**
1. Measure face geometry → design in **Fusion 360** (free for students)
2. Start with cheap safety glasses as base frame
3. Design clip-on camera + IR LED mounts as separate pieces
4. Material: PETG (flexible, durable) or Nylon (professional)
5. Reference: [Printables.com](https://printables.com) search "eye tracker mount", [GrabCAD](https://grabcad.com) search "glasses frame"

**IR LED setup:**
- 850nm wavelength, 2-4 LEDs per eye, 20-50mA each
- Driven via RPi 5 GPIO + transistor circuit (3.3V logic → LED driver)
- Must comply with IEC 62471 eye safety standard

**Where to learn:**
- Fusion 360: [autodesk.com/products/fusion-360](https://www.autodesk.com/products/fusion-360/overview) (free edu license)
- RPi GPIO: [raspberrypi.com/documentation/computers/raspberry-pi.html#gpio](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- EyeTrackVR hardware guide (IR LEDs, camera mods): [docs.eyetrackvr.dev](https://docs.eyetrackvr.dev/)
- Open-source glasses frames: [github.com/Makeroni/Eye-of-Horus](https://github.com/Makeroni/Eye-of-Horus)

---

### L6. Software Application (Web Dashboard)

**Architecture:**
```
RPi 5 (Edge Device)                    User's Browser
┌─────────────────────┐               ┌──────────────────┐
│ FastAPI Backend      │◄──WiFi/LAN──►│ Web Dashboard     │
│ ├── /api/start       │   WebSocket   │ ├── Live Preview  │
│ ├── /api/stop        │               │ ├── Session Mgmt  │
│ ├── /api/status      │               │ ├── FPS Monitor   │
│ └── /ws/live-feed    │               │ └── Data Download  │
│                      │               └──────────────────┘
│ Capture Pipeline     │
│ ├── libcamera/V4L2   │
│ ├── Multiprocessing  │
│ └── SSD Storage      │
└─────────────────────┘
```

**Tech stack:**
| Layer | Technology | Why |
|---|---|---|
| Backend | **FastAPI** (Python) | Async, fast, native WebSocket, runs on RPi 5 |
| Real-time | **WebSocket + SSE** | Live camera preview + FPS streaming |
| Frontend | **HTML + HTMX + Chart.js** | Lightweight, no heavy JS framework needed |
| Camera API | `libcamera` (CSI) / `linuxpy` (USB) | Direct hardware access |
| Process mgmt | `multiprocessing` + `systemd` | Auto-start on boot, crash recovery |

**Where to learn:**
- FastAPI: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- HTMX: [htmx.org](https://htmx.org/)
- Chart.js: [chartjs.org](https://www.chartjs.org/)
- WebSocket streaming: search "FastAPI WebSocket video stream raspberry pi"

---

### L7. Gaze Estimation Pipeline

**Full processing chain:**
```
Eye Frame → Preprocessing → Pupil Detection → Gaze Vector → Calibration Map → Scene Projection → Heatmap
```

| Stage | Method | Library |
|---|---|---|
| Preprocessing | Grayscale, histogram equalization, crop ROI | OpenCV |
| Pupil detection | PuRe ellipse fitting OR MediaPipe iris | OpenCV / MediaPipe |
| Gaze vector | Geometric eyeball model (pupil center → 3D ray) | NumPy / custom |
| Calibration | 9-point calibration → homography matrix | `cv2.findHomography()` |
| Scene mapping | Project gaze ray onto front camera frame | `cv2.perspectiveTransform()` |
| Heatmap | Accumulate gaze points → Gaussian kernel density | `scipy.ndimage` / OpenCV |
| Filtering | Kalman filter for jitter smoothing | `filterpy` |

**Where to learn:**
- gazeMapper: [github.com/dcnieho/gazeMapper](https://github.com/dcnieho/gazeMapper)
- EyeTrax: [github.com/ck-zhang/eyetrax](https://github.com/ck-zhang/eyetrax)
- Homography explained: OpenCV docs "Basic concepts of the homography"
- Niehorster et al. (2020) — slippage impact paper (already in your `/research/` folder)

---

## RPi 5 Hardware Reference

| Spec | Detail |
|---|---|
| SoC | BCM2712, Quad Cortex-A76 @ 2.4GHz |
| RAM | 4GB / 8GB LPDDR4X |
| GPU | VideoCore VII (OpenGL ES 3.1, Vulkan 1.2) |
| USB | 2× USB 3.0 (5Gbps) + 2× USB 2.0, **2 independent controllers** |
| CSI | **2× 22-pin 4-lane MIPI CSI-2** (1.5Gbps/lane) — dual camera native |
| GPIO | 40-pin, 28 multi-function pins, 3.3V logic |
| Power | 27W USB-C PD required for full USB current (1.6A total) |
| Video decode | 4Kp60 HEVC hardware decode |
| Storage | microSD + NVMe via HAT (recommended for data) |

> [!IMPORTANT]
> The RPi 5's **dual CSI ports** are a game-changer vs Kexxu's USB approach. Your custom prototype should use CSI cameras — this eliminates the USB bandwidth contention issue (Unknown U1) entirely.

---

## 10-Week Schedule

### Phase 1: Foundation (Weeks 1-3)

#### Week 1 — Environment Setup & Knowledge Ramp
| Task | Owner | Details |
|---|---|---|
| RPi 5 setup (all 5 boards) | All | Flash Raspberry Pi OS Bookworm, update, install dev tools |
| Git repo + branching strategy | Lead | Monorepo, `main`/`dev`/feature branches |
| USB/CSI theory session | All | Team study: USB 3.0 protocol, MIPI CSI-2, V4L2 API |
| Camera inventory | HW team | Test all available cameras (Kexxu USB + any CSI modules) |
| Reproduce existing pipeline | SW team | Get `capture_pipeline.py` running on RPi 5 with Kexxu cameras |

**Deliverable:** All 5 RPi 5s configured, pipeline running, team understands interfaces.

#### Week 2 — Camera Selection & First CSI Tests
| Task | Owner | Details |
|---|---|---|
| Order CSI cameras | HW team | OV7251/OV9281 (eye) + RPi Camera Module 3 (scene) |
| Port pipeline to RPi 5 | SW team | Adapt `capture_pipeline.py` for `libcamera` (CSI) + `linuxpy` (USB) |
| OpenCV + MediaPipe install | ML team | Set up CV environment, run first pupil detection on sample images |
| Data format spec finalization | All | Confirm CSV schema, MKV container, metadata format |
| FastAPI skeleton | Web team | Basic `/api/status` endpoint running on RPi 5 |

**Deliverable:** CSI cameras ordered, dual-interface pipeline skeleton, first pupil detection test.

#### Week 3 — Dual Camera Capture on RPi 5
| Task | Owner | Details |
|---|---|---|
| CSI dual-camera capture | HW+SW | Both CSI cameras streaming simultaneously via `libcamera`/`Picamera2` |
| USB dual-camera capture (Kexxu) | SW team | Validate Kexxu cameras on RPi 5 USB (fix FPS issue) |
| IR LED circuit design | HW team | Schematic: GPIO → transistor → 850nm LEDs, breadboard prototype |
| Timestamp synchronization analysis | SW team | Script to compute inter-frame jitter, plot distributions |
| Web dashboard: live preview | Web team | WebSocket video stream from camera to browser |

**Deliverable:** Both capture paths (CSI + USB) working on RPi 5, IR LED prototype on breadboard.

---

### Phase 2: Hardware Prototype (Weeks 4-6)

#### Week 4 — 3D Frame Design v1
| Task | Owner | Details |
|---|---|---|
| Frame CAD design | HW team | Fusion 360: safety glasses base + camera/LED mounts |
| First 3D print | HW team | PLA rapid prototype, test fit on team members |
| PuRe algorithm implementation | ML team | Port PuRe pupil detection to Python/OpenCV, test on eye images |
| Capture pipeline: CSI + USB abstraction | SW team | Single pipeline supporting both camera interfaces |
| Web dashboard: session management | Web team | Start/stop recording, session naming, file listing |

**Deliverable:** First 3D-printed frame, PuRe running on sample data.

#### Week 5 — Integration & IR Testing
| Task | Owner | Details |
|---|---|---|
| Mount cameras + LEDs on frame | HW team | Attach OV7251 + IR LEDs to 3D-printed clips |
| IR illumination testing | HW+ML | Verify pupil contrast under IR, tune LED current |
| End-to-end capture test | All | Full session: glasses on face → RPi 5 → SSD → data files |
| Gaze calibration: 9-point procedure | ML team | Implement calibration routine, compute homography |
| Web dashboard: live FPS + metrics | Web team | Real-time FPS, frame count, jitter display |

**Deliverable:** Wearable prototype v1 capturing data, calibration working.

#### Week 6 — Frame Iteration & Software Polish
| Task | Owner | Details |
|---|---|---|
| Frame v2 (refined fit) | HW team | Iterate based on comfort feedback, PETG material |
| Cable routing solution | HW team | Design cable channel along temple arm |
| Gaze mapping to scene | ML team | Project pupil position → front camera frame coordinates |
| Pipeline reliability testing | SW team | 30-min endurance test, frame drop analysis |
| Web: session review page | Web team | Playback recorded video + overlay gaze point |

**Deliverable:** Refined prototype, gaze-to-scene mapping working, 30-min sessions stable.

---

### Phase 3: Post-Processing & Cloud (Weeks 7-8)

#### Week 7 — Offline Processing Pipeline
| Task | Owner | Details |
|---|---|---|
| Batch processing script | ML team | Read MKV + CSV → detect pupils → output gaze coordinates |
| Heatmap generation | ML team | Accumulate gaze points → Gaussian KDE → overlay on scene |
| Cloud environment setup | SW team | Docker container with OpenCV + PyTorch, test on Colab/Vast.ai |
| ML model training (optional) | ML team | Train YOLOv8-nano pupil detector on collected eye images |
| Web: data upload to cloud | Web team | API endpoint to push session data to cloud storage |

**Deliverable:** Offline pipeline producing heatmaps, cloud environment ready.

#### Week 8 — Cloud Integration & Analysis
| Task | Owner | Details |
|---|---|---|
| Cloud batch processing | SW+ML | Upload session → cloud GPU processes → download results |
| 30fps vs 60fps comparison study | ML team | Quantify detection accuracy at different frame rates |
| MJPEG vs H.264 quality analysis | ML team | Compare pupil detection accuracy across formats |
| Web: results visualization | Web team | Display heatmaps, gaze traces, session statistics |
| Documentation: architecture diagrams | All | Update system concept docs for both prototypes |

**Deliverable:** Cloud pipeline working end-to-end, first research results.

---

### Phase 4: Integration & Validation (Weeks 9-10)

#### Week 9 — Full System Integration
| Task | Owner | Details |
|---|---|---|
| Kexxu prototype: full pipeline test | All | Kexxu glasses → RPi 5 → capture → cloud → heatmap |
| Custom prototype: full pipeline test | All | Custom glasses → RPi 5 → capture → cloud → heatmap |
| Side-by-side comparison | All | Same inspection task with both prototypes |
| Web dashboard: final features | Web team | Polish UI, add error handling, mobile-responsive |
| Bug fixes & edge cases | All | Handle camera disconnects, SSD full, thermal throttle |

**Deliverable:** Both prototypes running full end-to-end pipeline.

#### Week 10 — Documentation & Planning
| Task | Owner | Details |
|---|---|---|
| Technical report | All | Document all design decisions, test results, learnings |
| Demo video recording | All | Record demo of both prototypes in action |
| Next-semester planning | All | Identify gaps, plan FYP-II priorities |
| Bill of materials (BOM) | HW team | Final cost breakdown for custom prototype |
| Codebase cleanup + README | SW team | Clean code, docstrings, setup instructions |

**Deliverable:** Complete documentation, demo-ready system, clear FYP-II roadmap.

---

## Team Role Assignments (5 members)

| Role | Focus Areas | Key Skills to Build |
|---|---|---|
| **HW Lead** | Camera selection, 3D frame design, IR LEDs, GPIO circuits | Fusion 360, soldering, RPi GPIO, IEC 62471 |
| **Embedded SW Lead** | Capture pipeline, V4L2/libcamera, RPi 5 optimization | Python multiprocessing, V4L2 API, Linux kernel, systemd |
| **ML/CV Lead** | Pupil detection, gaze estimation, calibration, heatmaps | OpenCV, MediaPipe, PuRe, PyTorch, NumPy |
| **Web/App Lead** | Dashboard, API, real-time streaming, session management | FastAPI, WebSocket, HTMX, Chart.js, HTML/CSS |
| **Systems/Integration Lead** | Cloud setup, Docker, CI/CD, testing, documentation | Docker, GCP/Vast.ai, Git, pytest, technical writing |

> [!TIP]
> Everyone should understand the basics of ALL areas. Dedicate Week 1 to cross-training. Each person should be able to run the capture pipeline and explain the data flow.

---

## Software Architecture (supports both prototypes)

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  FastAPI Web Dashboard (session control, live monitoring)    │
├─────────────────────────────────────────────────────────────┤
│                    PIPELINE LAYER                            │
│  CaptureManager (abstraction over camera backends)           │
│  ├── USBCameraBackend (linuxpy/V4L2 — for Kexxu)           │
│  └── CSICameraBackend (Picamera2/libcamera — for custom)    │
├─────────────────────────────────────────────────────────────┤
│                    PROCESSING LAYER                          │
│  ├── PupilDetector (PuRe + optional ML fallback)            │
│  ├── GazeEstimator (geometric model + calibration)          │
│  ├── TemporalAligner (timestamp-based eye↔scene matching)   │
│  └── HeatmapGenerator (KDE accumulation on scene)           │
├─────────────────────────────────────────────────────────────┤
│                    STORAGE LAYER                             │
│  ├── LocalStorage (SSD: MKV + CSV per session)              │
│  └── CloudUploader (rsync/API to GCP/Vast.ai)              │
├─────────────────────────────────────────────────────────────┤
│                    HARDWARE LAYER                            │
│  Raspberry Pi 5 (BCM2712, 2×CSI, 2×USB3, GPIO for IR LEDs) │
└─────────────────────────────────────────────────────────────┘
```

The key design principle: **one software system, two hardware backends**. The `CaptureManager` abstract class lets you swap between Kexxu USB cameras and custom CSI cameras without changing any downstream code.

---

## Bill of Materials (Estimated)

| Item | Qty | Unit Price | Total | Notes |
|---|---|---|---|---|
| Raspberry Pi 5 (8GB) | 2 | ~$80 | $160 | One per prototype |
| RPi 5 27W USB-C PSU | 2 | ~$12 | $24 | Required for full USB power |
| Innomaker OV7251 (CSI, global shutter) | 2 | ~$25 | $50 | Eye camera for custom prototype |
| RPi Camera Module 3 NoIR | 1 | ~$35 | $35 | Scene camera for custom |
| CSI ribbon cables (22-pin) | 4 | ~$5 | $20 | Spares |
| 850nm IR LEDs | 10 | ~$0.50 | $5 | 4 per eye + spares |
| Resistors, transistors, PCB | 1 lot | ~$15 | $15 | LED driver circuit |
| Safety glasses (base frame) | 3 | ~$5 | $15 | For prototyping |
| 3D printing filament (PETG) | 1kg | ~$25 | $25 | Frame + mounts |
| External SSD (256GB) | 1 | ~$30 | $30 | Session data storage |
| Powered USB 3.0 Hub | 1 | ~$25 | $25 | For Kexxu prototype |
| NVMe HAT + SSD (for RPi) | 1 | ~$40 | $40 | Fast local storage |
| **TOTAL** | | | **~$444** | |

---

## Key Open-Source References

| Resource | URL | Use |
|---|---|---|
| Pupil Labs (software) | github.com/pupil-labs/pupil | Reference architecture for eye tracking |
| EyeTrackVR | github.com/EyeTrackVR/EyeTrackVR | DIY IR camera + LED hardware guides |
| gazeMapper | github.com/dcnieho/gazeMapper | Wearable gaze → world coordinate mapping |
| glassesTools | github.com/dcnieho/glassesTools | Multi-brand glasses data processing |
| Eye-of-Horus | github.com/Makeroni/Eye-of-Horus | Open-source assistive eye tracker CAD |
| Awesome Eye Tracking | github.com/eyes-on-disabilities/awesome-eye-tracking | Curated list of everything |
| EyeTrax | github.com/ck-zhang/eyetrax | Modern Python eye tracking package |
| Picamera2 | github.com/raspberrypi/picamera2 | RPi 5 camera Python library |

---

## Critical Decisions to Make Early

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Eye camera for custom prototype | OV7251 vs OV9281 vs RPi GS Camera | **OV9281** — 1MP global shutter, IR NoIR, CSI, good balance |
| 2 | Scene camera | RPi Cam 3 NoIR vs USB webcam | **RPi Camera Module 3** via CSI (no USB contention) |
| 3 | On-device vs cloud processing | Real-time on RPi vs batch on cloud | **Capture on RPi, heavy ML on cloud** — RPi 5 can do PuRe in real-time for live preview, but train/run CNN models on cloud |
| 4 | Web app vs mobile app | Browser dashboard vs native Android/iOS | **Web app** — works on any device, no app store, easier to build |
| 5 | Storage medium on RPi 5 | microSD vs NVMe HAT vs external SSD | **NVMe HAT** for custom prototype (fastest), USB SSD for Kexxu |
| 6 | Operating system | Raspberry Pi OS vs Ubuntu | **Raspberry Pi OS Bookworm** — best camera support via libcamera |
