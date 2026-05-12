# Component 2: Embedded System & Data Capture Pipeline
## Technical Onboarding Document

Welcome to the team! This document serves as your technical onboarding guide for **Component 2: Embedded System & Data Capture Pipeline** of the Toyota-Kexxu Eye Tracking Glasses project. 

Your primary focus will be on reliable signal acquisition, low-level camera interfacing, managing real-time constraints, and ensuring precise synchronization and timestamping of the data pipeline.

---

## 1. System Architecture & Design Philosophy

### Decoupled Physical Architecture
Head-mounted eye-tracking (HMET) systems face strict ergonomic, weight, and thermal constraints. Research indicates that heavy head units or excessive thermal loads cause discomfort and introduce **slippage**—even a 2-3mm shift in the glasses can invalidate the angular calibration of the eye tracker.

To mitigate this, we employ a **decoupled architecture**:
- **Head Unit (Glasses):** Only houses the lightweight USB cameras and IR illuminators. 
- **Waist-Mounted/Pocket Case:** Houses the embedded System-on-Chip (SoC), power delivery, and storage. This protects the user from thermal throttling heat and significantly reduces the weight on the face.

### Hardware Specifications
- **Eye Camera (Microdia/Sonix):** Tracks eye gaze at `1280x800 @ 60 FPS (MJPG)`. High temporal resolution is required to capture rapid saccades.
- **Front/Scene Camera (Realtek):** Captures the world view at `1280x720 @ 30 FPS (MJPG)`. 
- **Storage:** External SSD for high-bandwidth, direct-to-disk run-time storage.
- **Power:** External high-capacity Li-ion battery pack designed to last 5-6 hours.

---

## 2. Embedded Software Pipeline

Our capture pipeline is designed to bypass high-level overhead (like OpenCV or GStreamer processing delays) to ensure deterministic frame capture and minimize OS jitter. 

### Direct Device Access (V4L2)
We utilize **Video4Linux2 (V4L2)** to interface directly with the USB Video Class (UVC) cameras.
- The cameras output native **MJPEG** compressed frames. Capturing in native MJPEG passes the compression workload to the camera's internal hardware, saving immediate CPU overhead on the embedded SoC.
- **Producer-Consumer Buffer:** Our python script (`capture_pipeline.py`) pulls frames directly from kernel memory (zero-copy DMA) and writes the raw MJPEG bytes straight to an `.mkv` container on the SSD. This is the fastest possible way to write data with near-zero CPU overhead.

### Multiprocessing & Synchronization
- We use Python's `multiprocessing` module to run each camera stream on a dedicated CPU core.
- Both threads wait for a shared `multiprocessing.Event` flag to start recording simultaneously, ensuring synchronous data capture from the beginning of the session.

---

## 3. Timestamping & Jitter Mitigation

When running dual USB cameras, OS Jitter (CPU load causing software timestamps to fluctuate by 3-15ms) is the biggest threat to data quality. Dropped frames or inaccurate timestamps destroy the synchronization required to map gaze vectors to the scene.

### Monotonic Timestamping
Instead of relying on user-space time, we extract kernel-level `v4l2_buffer` metadata. 
- Every frame receives a nanosecond-precision tag at the kernel dequeue boundary using `CLOCK_MONOTONIC`. This makes the timestamps immune to NTP jumps and user-space scheduling delays.
- We leave a safety buffer in the exposure times. For instance, the 60FPS eye camera (16.6ms window) has its exposure strictly locked to `15.7ms` (via `v4l2-ctl`). This gives the Image Signal Processor (ISP) ~1ms to package and transmit data over the USB bus without missing the polling window.

---

## 4. Setup, Configuration, and SOPs

### Udev Rules
To ensure consistent device nodes regardless of the plug-in order, we use udev rules to symlink the hardware to `/dev/eye` and `/dev/front`.

*Activation:*
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=video4linux
```
*Verification:* `ls -l /dev/eye /dev/front`

### Manual Exposure Control
Auto-exposure can ruin frame rates in low light. We lock the exposure values using `v4l2-ctl` before starting the pipeline:
```bash
v4l2-ctl -d /dev/eye --set-ctrl=auto_exposure=1 --set-ctrl=exposure_time_absolute=157
v4l2-ctl -d /dev/front --set-ctrl=auto_exposure=1 --set-ctrl=exposure_time_absolute=166
```
*(Note: If the image is too dark, do not increase exposure time. Increase the gain (`--set-ctrl=gain=50`) instead.)*

### Power and SSD Constraints
- **Critical Requirement:** USB ports on standard laptops/SBCs usually provide only ~0.9 Amps. Dual cameras and an external SSD will pull up to 2.0 Amps, leading to brown-outs and disconnects.
- **SOP:** Always use a **Powered USB Hub** (plugged into a wall outlet) or distribute the load across different internal USB controllers.
- Never unplug the SSD while the script is running. Always wait for the graceful shutdown message to prevent corrupted video handles and lost metadata.

---

## 5. Deliverables & Output Formats

At the end of a supervised or un-supervised session, the pipeline generates the following strictly structured data on the SSD:

1. **Video Containers:**
   - `eye.mkv` (MJPG, 1280x800, 60fps)
   - `front.mkv` (MJPG, 1280x720, 30fps)
2. **High-Precision Metadata:**
   - `eye_timestamps.csv` (frame_index, timestamp_ns)
   - `front_timestamps.csv` (frame_index, timestamp_ns)
   - `session_meta.csv` (camera_label, start_time_ns, end_time_ns, total_frames)
