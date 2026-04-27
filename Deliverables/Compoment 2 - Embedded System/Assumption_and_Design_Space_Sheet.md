# Assumption Mapping and Design Space Exploration

## Component 2: Embedded System & Data Capture Pipeline
### Primary Focus: Camera Data Extraction Pipeline

**Project:** Toyota Eye Wear — Wearable Eye-Tracking System  
**Date:** February 21, 2026  
**Stage:** Requirements — Design Space Exploration (Pre-Concept Selection)

---

## 1. Core System Functions

The camera data extraction pipeline for the wearable eye-tracking system is decomposed into the following **six core functions**. Each function addresses a distinct engineering responsibility within the pipeline, from hardware interfacing through to data export.

| # | Core Function | Description |
|---|---------------|-------------|
| F1 | **Camera Interfacing & Signal Acquisition** | Establishing a reliable communication link between the embedded processor and camera modules (eye camera + scene camera), negotiating formats, and acquiring raw image data |
| F2 | **Frame Rate & Resolution Management** | Controlling and sustaining stable capture parameters (resolution, FPS, pixel format) under varying thermal and computational load conditions |
| F3 | **Timestamping & Temporal Alignment** | Assigning each acquired frame a precise, monotonically increasing timestamp and maintaining temporal coherence between dual camera streams |
| F4 | **Buffering & Flow Control** | Decoupling frame acquisition from downstream processing/storage to absorb transient latency spikes and prevent frame loss |
| F5 | **Encoding & Local Storage** | Compressing and persisting video streams and structured metadata to onboard storage in a format suitable for later analysis |
| F6 | **Data Export & Transfer** | Moving recorded sessions from the embedded device to an external system for post-processing, analysis, and archival |

---

## 2. Design Space Exploration — Mechanisms per Core Function

> **Note:** No concept selection is intended at this stage. The purpose is to establish the breadth of possible mechanisms and understand fundamental trade-offs.

---

### F1 — Camera Interfacing & Signal Acquisition

**Problem Statement:** How does the embedded system physically receive image data from camera sensors?

#### Mechanism A: V4L2 (Video4Linux2) Direct Device Access

| Aspect | Detail |
|--------|--------|
| **Principle** | User-space application opens `/dev/videoX` device nodes, uses `ioctl` calls to negotiate format (MJPG/YUYV, resolution, FPS), and uses `mmap`-based streaming to dequeue frames from kernel buffers |
| **Strengths** | Industry-standard Linux camera API; mature driver support via `uvcvideo`; fine-grained control over exposure, white balance, and capture parameters; direct access to UVC metadata stream (`/dev/video3` UVCH payload headers) |
| **Weaknesses** | Requires Linux-specific knowledge; limited portability; user-space scheduling delays can affect determinism; driver-level bugs hard to debug |
| **Relevance** | Directly applicable — the Kexxu hardware cameras are confirmed UVC-compliant through `/dev/video2` and `/dev/video3`, and V4L2 has already been tested successfully |

#### Mechanism B: GStreamer Multimedia Framework

| Aspect | Detail |
|--------|--------|
| **Principle** | A pipeline-based multimedia framework constructs a directed graph of elements: `v4l2src → queue → videoconvert → encoder → filesink`. The framework manages buffer allocation, format negotiation, and threading internally |
| **Strengths** | Higher-level abstraction reduces boilerplate; automatic format negotiation; built-in multi-threading; native hardware acceleration plugins for encoding; well-suited for complex multi-branch pipelines (e.g., tee for display + record) |
| **Weaknesses** | Added abstraction layer introduces latency and reduced control over exact buffer timing; debugging pipeline stalls is non-trivial; dependency footprint is larger; less granular timestamp control compared to raw V4L2 |
| **Relevance** | Strong candidate for production pipelines; commonly used in Jetson/embedded vision systems; would reduce implementation complexity at some cost to timestamp precision |

#### Mechanism C: OpenCV VideoCapture Abstraction

| Aspect | Detail |
|--------|--------|
| **Principle** | Uses `cv2.VideoCapture(device_id)` to open camera and `cap.read()` to pull frames as NumPy arrays. OpenCV internally wraps V4L2 or FFmpeg backends |
| **Strengths** | Extremely simple API; fastest path to a working prototype; natural integration with downstream computer vision processing (pupil detection, gaze estimation); cross-platform |
| **Weaknesses** | Least control over buffer management, timestamping, and format negotiation; `cap.read()` is blocking and single-threaded by default; no access to UVC metadata; hides critical camera state; unreliable for sustained high-FPS capture without custom threading |
| **Relevance** | Excellent for rapid prototyping and algorithm development; likely insufficient for production-grade deterministic capture without significant wrapper engineering |

#### Mechanism D: MIPI CSI Direct Interface (Hardware-Level)

| Aspect | Detail |
|--------|--------|
| **Principle** | Camera sensor connects via MIPI CSI-2 lanes directly to the SoC's ISP (Image Signal Processor). Frames are DMA'd into memory with minimal CPU involvement. Accessed via platform-specific V4L2 media controller or proprietary SDK (e.g., NVIDIA Argus/LibArgus) |
| **Strengths** | Lowest latency; highest throughput; hardware-level frame synchronization possible via GPIO trigger; zero USB bandwidth constraints; deterministic timing |
| **Weaknesses** | Requires MIPI-compatible cameras and embedded boards with CSI connectors; more complex driver setup; platform-dependent; current Kexxu cameras are USB-based, so this would require hardware changes |
| **Relevance** | Represents the optimal long-term path for a wearable product; not applicable to current USB-based Kexxu camera hardware without redesign |

---

### F2 — Frame Rate & Resolution Management

**Problem Statement:** How does the system maintain consistent and stable capture parameters over extended recording sessions?

#### Mechanism A: Fixed Negotiation at Session Start (Static Configuration)

| Aspect | Detail |
|--------|--------|
| **Principle** | At session initialization, explicitly set resolution, FPS, and pixel format via V4L2 `ioctl` (`VIDIOC_S_FMT`, `VIDIOC_S_PARM`). Lock auto-exposure and auto-white-balance to fixed values. Maintain these settings throughout the session |
| **Strengths** | Maximally deterministic; eliminates frame rate variations caused by auto-exposure adjustments; simplest to implement and debug; produces consistent data for research analysis |
| **Weaknesses** | Cannot adapt to changing illumination conditions (problematic for wearable use in varied environments); fixed settings may produce poor image quality in edge cases; requires manual tuning per environment |
| **Relevance** | Best-fit for controlled lab recording sessions; aligns with the current development phase of desk-based pipeline testing |

#### Mechanism B: Adaptive Resolution/FPS Scaling (Dynamic Degradation)

| Aspect | Detail |
|--------|--------|
| **Principle** | Monitor CPU load, thermal state, and buffer occupancy in real-time. When thresholds are exceeded, gracefully reduce resolution (e.g., 1280×800 → 640×480) or FPS (e.g., 60 → 30) to maintain pipeline stability. Scale back up when conditions improve |
| **Strengths** | Prevents catastrophic frame drops and thermal throttling; graceful degradation preserves some data even under stress; extends battery life on portable devices |
| **Weaknesses** | Variable resolution/FPS complicates downstream analysis; synchronization logic must handle changing frame intervals; more complex implementation; may produce inconsistent datasets |
| **Relevance** | Important for future wearable deployment where power and thermal budgets are constrained; premature for current development stage |

#### Mechanism C: Multi-Profile Capture with User Selection

| Aspect | Detail |
|--------|--------|
| **Principle** | Pre-define a set of capture profiles (e.g., "High Quality": 1280×800@60fps MJPG, "Balanced": 1280×720@30fps, "Endurance": 640×480@30fps). User selects profile before recording. Profile determines all capture parameters and expected performance characteristics |
| **Strengths** | Predictable behavior per profile; enables research on sampling-rate-vs-performance tradeoffs (30 Hz vs 60 Hz); simple for users; profiles can be documented and reproducible |
| **Weaknesses** | No mid-session adaptation; requires empirical characterization of each profile's thermal/stability behavior; profile design requires upfront testing effort |
| **Relevance** | Directly supports the deliverable of "sampling rate vs. performance" research contribution; allows systematic benchmarking |

---

### F3 — Timestamping & Temporal Alignment

**Problem Statement:** How are frames assigned precise timing information, and how is temporal coherence maintained between the dual camera streams?

#### Mechanism A: Software Monotonic Clock Stamping

| Aspect | Detail |
|--------|--------|
| **Principle** | Immediately upon dequeueing each frame from the V4L2 buffer, record `clock_gettime(CLOCK_MONOTONIC)` in nanoseconds. Store `{frame_id, camera_id, timestamp_ns}` in a structured metadata log. Synchronization between cameras is performed post-hoc by matching nearest timestamps |
| **Strengths** | Simple to implement; no hardware dependencies; `CLOCK_MONOTONIC` is immune to NTP jumps and user clock changes; sufficient for many research applications; already identified as the primary strategy in current architecture |
| **Weaknesses** | Subject to software scheduling jitter (microseconds to low milliseconds); inter-camera alignment depends on thread scheduling fairness; accuracy degrades under high CPU load; cannot distinguish between capture time and dequeue time |
| **Relevance** | The baseline approach; currently planned for implementation; adequate for initial pipeline validation and drift analysis |

#### Mechanism B: UVC Payload Header Hardware Metadata

| Aspect | Detail |
|--------|--------|
| **Principle** | The scene camera's `/dev/video3` node exposes UVC Payload Header Metadata (UVCH format, 10240-byte buffer). This metadata can contain Source Clock Reference (SCR) fields and Presentation Time Stamps (PTS) embedded by the camera's own clock. These hardware-level timestamps are extracted and correlated with the software monotonic timestamps |
| **Strengths** | Provides frame-level timing from hardware closer to actual exposure; can reveal USB scheduling delays invisible to software timestamps; enables accurate measurement of camera-to-host latency; unique differentiator for research publication |
| **Weaknesses** | Not all UVC cameras populate PTS/SCR fields with valid data; requires parsing raw UVCH packets; camera clock may drift relative to host `CLOCK_MONOTONIC`; currently unvalidated on the Kexxu eye camera; added implementation complexity |
| **Relevance** | High-value research opportunity; the scene camera's metadata stream has been discovered but not yet validated for timestamp content; warrants systematic evaluation |

#### Mechanism C: Hardware Trigger Synchronization (External Sync Signal)

| Aspect | Detail |
|--------|--------|
| **Principle** | An external GPIO signal (from the embedded board or a dedicated sync pulse generator) simultaneously triggers both cameras to capture frames. Both cameras begin exposure at the exact same electrical edge, ensuring sub-microsecond temporal alignment |
| **Strengths** | Gold-standard synchronization accuracy (sub-microsecond); eliminates software timing uncertainty entirely; well-proven in robotics and multi-camera research systems; makes gaze-to-world mapping maximally accurate |
| **Weaknesses** | Requires cameras that support external trigger input (GPIO or strobe); USB UVC cameras typically do not expose hardware trigger pins; requires custom wiring; adds hardware complexity; the current Kexxu cameras may not support this mode |
| **Relevance** | Represents the ideal long-term solution if cameras are upgraded to models with trigger support (e.g., FLIR, IDS, Basler industrial cameras); not feasible with current USB UVC hardware |

#### Mechanism D: Network Time Protocol (PTP/NTP) Distributed Clock Sync

| Aspect | Detail |
|--------|--------|
| **Principle** | If cameras or processors are network-connected, use IEEE 1588 Precision Time Protocol (PTP) or NTP to synchronize clocks across distributed nodes. Each device timestamps with its synchronized clock |
| **Strengths** | Scalable to many devices; well-standardized; microsecond accuracy with PTP; applicable to distributed sensor setups |
| **Weaknesses** | Requires network infrastructure; PTP requires hardware support for best accuracy; massive overkill for a two-camera wearable; added complexity with no proportional benefit for the current system scope |
| **Relevance** | Not applicable to the current single-board dual-camera architecture; included for design space completeness |

---

### F4 — Buffering & Flow Control

**Problem Statement:** How is the pipeline protected against transient processing delays, disk I/O stalls, and encoder backlogs that would otherwise cause frame loss?

#### Mechanism A: Per-Camera Ring Buffer (Bounded Queue)

| Aspect | Detail |
|--------|--------|
| **Principle** | Each camera's capture thread writes into a fixed-size circular (ring) buffer. A separate consumer thread (encoder/writer) reads from the other end. When the buffer is full, the oldest unprocessed frame is overwritten, ensuring the capture thread is never blocked |
| **Strengths** | Fixed memory footprint; deterministic behavior; decouples producer and consumer timing; classic real-time systems pattern; prevents pipeline stall propagation |
| **Weaknesses** | Overwrites oldest frames on overflow — data loss is silent unless monitored; buffer size must be tuned (too small → frequent loss, too large → memory pressure); requires thread-safe implementation (lock-free queues or mutexes) |
| **Relevance** | The recommended and most commonly used approach for vision pipelines; already planned in the current architecture (Layer 4) |

#### Mechanism B: Unbounded Queue with Backpressure Signaling

| Aspect | Detail |
|--------|--------|
| **Principle** | Frames are enqueued into a dynamically growing queue. When queue depth exceeds a threshold, a backpressure signal instructs the capture thread to reduce FPS or skip frames intentionally. Normal speed resumes when the queue drains below a lower threshold |
| **Strengths** | No silent frame loss — frames are either captured or explicitly skipped with a logged decision; allows temporary bursts of storage delay without data loss; provides runtime metrics (queue depth) for latency analysis |
| **Weaknesses** | Memory consumption is unpredictable; can cause OOM on memory-constrained embedded systems; backpressure logic adds complexity; may cause capture instability if FPS changes mid-stream |
| **Relevance** | Useful as a diagnostic/development mode to characterize worst-case latency behavior; not recommended for production due to memory unpredictability |

#### Mechanism C: V4L2 Kernel-Level Multi-Buffer (Zero-Copy DMA)

| Aspect | Detail |
|--------|--------|
| **Principle** | Allocate multiple V4L2 buffers (4–8) via `VIDIOC_REQBUFS` with `mmap`. The kernel cycles through these buffers, filling them with frame data via DMA while the application processes previously filled buffers. Frames are dequeued and re-enqueued in a continuous cycle |
| **Strengths** | Zero-copy from camera to user-space; minimal CPU overhead; inherent double/triple buffering at the driver level; low latency; no additional user-space buffer management needed for simple pipelines |
| **Weaknesses** | Buffer count is limited by driver and hardware; if user-space processing is slower than frame arrival, kernel buffers overflow and frames are silently dropped; less flexible for complex multi-consumer pipelines |
| **Relevance** | This is the fundamental mechanism underlying V4L2 streaming; should be used as the first layer regardless of additional user-space buffering choices |

---

### F5 — Encoding & Local Storage

**Problem Statement:** How are captured video streams compressed and persisted efficiently on the embedded device's storage?

#### Mechanism A: MJPEG Pass-Through (Camera-Side Compression)

| Aspect | Detail |
|--------|--------|
| **Principle** | The cameras output MJPEG-compressed frames natively. These compressed frames are written directly to disk in an MJPEG container (AVI) or individually as JPEG files, with no re-encoding on the embedded processor |
| **Strengths** | Zero CPU encoding overhead — compression happens inside the camera hardware; simplest implementation; frame-independent compression means any frame can be extracted individually; supports the highest camera FPS since MJPEG is the fast-path format (30 fps for scene, 60 fps for eye) |
| **Weaknesses** | MJPEG has poor compression efficiency (~10:1 vs H.264's ~50:1); storage fills much faster; no temporal compression (no inter-frame prediction); file sizes 3–5× larger than H.264 for equivalent quality |
| **Relevance** | Optimal for initial development — eliminates encoding as a variable when debugging the pipeline; storage is abundant during desk-based testing |

#### Mechanism B: Hardware H.264/H.265 Encoding (SoC Encoder)

| Aspect | Detail |
|--------|--------|
| **Principle** | Decode the incoming MJPEG frames, pass raw frames to the SoC's dedicated hardware video encoder (e.g., Jetson NVENC, Rockchip VPU, or Intel QSV). Output H.264/H.265 encoded MP4 files |
| **Strengths** | Dramatic storage savings (5–10× vs MJPEG); near-zero CPU overhead (hardware block does the work); industry-standard output format; enables longer recording sessions; produces files directly suitable for analysis tools |
| **Weaknesses** | Requires MJPEG decode + re-encode (added latency and CPU for decode step); hardware encoder availability depends on SoC choice; introduces encoding latency (typically 1–3 frames); more complex pipeline; encoder quality settings need tuning |
| **Relevance** | Essential for extended recording sessions and eventual wearable deployment; requires an embedded board with hardware encoder support |

#### Mechanism C: Lossless Frame Archival (Raw/PNG per Frame)

| Aspect | Detail |
|--------|--------|
| **Principle** | Save every captured frame as an individual lossless image file (PNG, TIFF, or raw binary dump) with an accompanying metadata JSON file. Frames are numbered sequentially and stored in session directories |
| **Strengths** | Maximum image fidelity — no compression artifacts; each frame independently accessible without video demuxing; simplest possible storage logic; ideal for algorithm development and ground-truth dataset creation |
| **Weaknesses** | Enormous storage requirements (1280×800 raw ≈ 1 MB/frame × 60 fps = 60 MB/s = 3.6 GB/min); disk I/O becomes the bottleneck; not sustainable for sessions longer than a few minutes on typical embedded storage; requires fast SSD or NVMe |
| **Relevance** | Useful for short, controlled capture bursts to build reference datasets for pupil detection benchmarking; impractical for normal operation |

#### Mechanism D: Segmented Container Recording with Rotation

| Aspect | Detail |
|--------|--------|
| **Principle** | Record into time-limited segments (e.g., 10-minute MP4 files). When a segment reaches the time/size limit, close it and begin a new segment. Each segment is self-contained and playable. Metadata JSONL logs reference segment boundaries |
| **Strengths** | Crash resilience — a system failure loses at most the current segment, not the entire session; easier to manage and transfer smaller files; enables concurrent upload of completed segments during recording; simpler post-processing parallelization |
| **Weaknesses** | Segment boundaries create small gaps or require careful handling to avoid frame loss at transitions; adds session management complexity; requires robust naming and metadata to reconstruct full sessions |
| **Relevance** | Professional best practice for long-duration recording; should be layered on top of whichever encoding mechanism is selected |

---

### F6 — Data Export & Transfer

**Problem Statement:** How are recorded sessions moved from the embedded wearable device to an external system for analysis?

#### Mechanism A: Physical Wired Transfer (USB/Ethernet File Copy)

| Aspect | Detail |
|--------|--------|
| **Principle** | After recording, connect the device via USB cable or Ethernet to a workstation. Mount the storage or use `scp`/`rsync` to copy session files |
| **Strengths** | Maximum transfer speed (USB 3.0: ~5 Gbps, Gigabit Ethernet: ~1 Gbps); zero packet loss; no wireless interference; simplest protocol; works offline |
| **Weaknesses** | Requires physical connection — interrupts wearable usage; not suitable for real-time streaming; manual workflow (connect, copy, disconnect); user must remember to export |
| **Relevance** | The recommended starting approach; aligns with offline-first development philosophy; sufficient for all development and initial research phases |

#### Mechanism B: WiFi-Based File Transfer / Streaming

| Aspect | Detail |
|--------|--------|
| **Principle** | The embedded device connects to a WiFi network and either (a) pushes completed session files via `rsync`/HTTP upload or (b) streams encoded video in real-time via RTSP/WebRTC to a receiving server |
| **Strengths** | Wireless convenience; can operate continuously without physical connection; enables near-real-time monitoring of recording sessions; supports remote supervision of experiments |
| **Weaknesses** | WiFi introduces jitter, packet loss, and variable latency; streaming requires additional network stack and encode-on-the-fly capability; bandwidth may be insufficient for dual-stream 60 fps; power-hungry; network environment not always available |
| **Relevance** | Useful for lab environments with reliable WiFi infrastructure; streaming mode is a future enhancement after offline pipeline stability is proven |

#### Mechanism C: Bluetooth Low Energy (BLE) for Metadata / Control

| Aspect | Detail |
|--------|--------|
| **Principle** | Use BLE to transfer lightweight data: gaze coordinates, session metadata, recording status, and device health telemetry. Video data is NOT transferred via Bluetooth — only control signals and small data packets |
| **Strengths** | Very low power; always-on connectivity for device status monitoring; can trigger recording start/stop from a phone; suitable for gaze coordinate streaming (small packets at ~30–60 Hz); standardized mobile compatibility |
| **Weaknesses** | Throughput far too low for video (BLE max ~2 Mbps theoretical, ~100–200 kbps sustained); not suitable for bulk data transfer; adds Bluetooth stack complexity; potential interference with other devices |
| **Relevance** | Appropriate for control signals and real-time gaze data export; explicitly NOT for video transfer; must be combined with another mechanism for full data export |

#### Mechanism D: Removable Storage Media (SD Card / USB Drive)

| Aspect | Detail |
|--------|--------|
| **Principle** | Record directly to a removable SD card or USB flash drive. After the session, physically remove the storage media and insert it into the analysis workstation |
| **Strengths** | Zero network dependency; zero transfer latency for end user; swap-and-continue recording with multiple cards; simple mental model; robust against network failures |
| **Weaknesses** | Mechanical wear on connectors; risk of data corruption from improper ejection; storage media speed variations (cheap SD cards may cause frame drops); limited capacity; manual workflow |
| **Relevance** | Common approach in field research devices (e.g., GoPro model); viable for wearable deployment if combined with robust file system handling and safe-eject protocols |

---

## 3. Environmental and Operational Assumptions

These assumptions define the boundaries within which the data capture pipeline is expected to operate. Any violation of these assumptions may invalidate design decisions.

### 3.1 Hardware Environment

| ID | Assumption | Basis |
|----|-----------|-------|
| A1 | The system uses **two USB UVC cameras** on a single embedded Linux board | Confirmed: ICT Camera (scene, USB) and USB 2.0 Camera (eye, USB) via V4L2 enumeration |
| A2 | The scene camera outputs **1920×1080 @ 30 fps in MJPEG** via `/dev/video2` | Confirmed via `v4l2-ctl` format enumeration and test recording (actual 29.96 fps over 20.66s) |
| A3 | The eye camera outputs **1280×800 @ 60 fps in MJPEG** via its respective `/dev/videoX` | Confirmed via `v4l2-ctl` format enumeration; sustained operation to be validated |
| A4 | Both cameras use the **uvcvideo** Linux kernel driver | Confirmed via `v4l2-ctl --all` output and media topology enumeration |
| A5 | The scene camera exposes a **UVC metadata node** (`/dev/video3`) with UVCH payload header format and 10240-byte buffer | Confirmed via device enumeration; data validity unvalidated |
| A6 | **USB bandwidth** is sufficient to sustain both cameras simultaneously (MJPEG) | Assumed but unvalidated — both cameras on the same USB root hub could cause bandwidth contention |
| A7 | The embedded board provides **hardware video encoding** capability (H.264/H.265) | Assumed if using Jetson Orin Nano; not confirmed for current development platform |
| A8 | Sufficient **local storage** (≥ 32 GB) is available for recording sessions | Assumed; storage type (eMMC, SSD, SD card) and write speed not yet characterized |

### 3.2 Operational Environment

| ID | Assumption | Basis |
|----|-----------|-------|
| A9 | Initial development and testing occurs in a **controlled desk/lab setting**, not on a moving person | Project plan: wearable deployment is a later phase |
| A10 | Recording sessions are **10–30 minutes** in the development phase | Based on typical eye-tracking study durations; extended endurance testing to follow |
| A11 | The system operates under **Ubuntu Linux** (Jetson default or standard x86) | Confirmed from development environment setup |
| A12 | Ambient temperature is within **15–35°C** (indoor lab conditions) | Assumed; thermal throttling behavior under higher ambient temperatures is unknown |
| A13 | The pipeline is **soft real-time** — occasional missed deadlines are tolerable, but sustained drops indicate failure | Stated in project notes; the system must detect and log degraded performance rather than crash |

### 3.3 Data & Downstream Processing

| ID | Assumption | Basis |
|----|-----------|-------|
| A14 | Captured data will be used for **offline post-processing** (pupil detection, gaze estimation, heatmap generation) — not real-time inference during initial phases | Project plan: capture pipeline precedes analysis pipeline |
| A15 | Accurate **frame-level timestamps** are mandatory for gaze-to-world mapping and inter-camera alignment | Fundamental system requirement; without timestamps, multi-stream data is scientifically unusable |
| A16 | The **metadata format** (JSONL with frame_id, camera_id, timestamp_ns, resolution, nominal_fps) is sufficient for initial pipeline validation | Defined in current architecture; may need extension for gaze data, exposure settings, and IMU data in later phases |
| A17 | Data consumers (analysis scripts) expect **standard formats**: MP4 (H.264) for video and JSONL for metadata | Industry convention; ensures toolchain compatibility (FFmpeg, OpenCV, Python) |

---

## 4. Unknowns That Could Invalidate a Concept

These are identified risks — open questions whose answers could fundamentally change the viability of one or more design mechanisms.

### 4.1 Critical Unknowns (High Impact)

| ID | Unknown | Affected Mechanisms | Potential Impact |
|----|---------|---------------------|------------------|
| U1 | **Can both USB cameras sustain full-rate capture simultaneously?** Both cameras share USB root hub bandwidth. MJPEG at 1080p30 + 800p60 may exceed USB 2.0's ~480 Mbps limit or cause scheduling conflicts | F1 (all USB-based mechanisms), F2 (sustained FPS) | If bandwidth is insufficient, one camera must reduce FPS or resolution. This could invalidate the assumption that 60 fps eye tracking is achievable with current hardware configuration |
| U2 | **Does the UVC metadata stream contain valid PTS/SCR timestamps?** The `/dev/video3` metadata node exists, but the actual content of the UVCH payload headers has not been validated | F3 Mechanism B (UVC metadata sync) | If PTS/SCR fields are zero or unsupported, hardware-based timestamp synchronization is unavailable, and software timestamps become the only option |
| U3 | **What is the actual inter-camera timestamp drift over extended sessions (10–60 min)?** Software timestamps from two independent capture threads on different USB devices will accumulate clock skew | F3 (all timestamp mechanisms) | If drift exceeds the inter-frame interval (~16.7 ms at 60 fps), temporal alignment becomes ambiguous, and gaze-to-world mapping degrades. This would force evaluation of hardware trigger or metadata-based alternatives |
| U4 | **Does the embedded board thermally throttle under sustained dual-camera capture?** Continuous video processing generates significant heat. Throttling reduces CPU frequency and can cascade into frame drops | F2, F4, F5 | If thermal throttling occurs within the first 10 minutes, all mechanisms assuming stable FPS throughout a session are invalidated. Active cooling or dynamic degradation would become mandatory |

### 4.2 Significant Unknowns (Medium Impact)

| ID | Unknown | Affected Mechanisms | Potential Impact |
|----|---------|---------------------|------------------|
| U5 | **What is the actual MJPEG decode overhead when re-encoding to H.264?** The cameras output MJPEG; H.264 encoding requires first decoding MJPEG to raw, then encoding to H.264 | F5 Mechanism B (H.264 re-encoding) | If MJPEG decode + H.264 encode exceeds ~10% CPU, the pipeline may not sustain 60 fps without hardware encoder support. This would force either MJPEG pass-through storage or reducing FPS |
| U6 | **What is the write speed of the target storage medium?** SD cards, eMMC, and NVMe SSDs have vastly different sustained write performance. MJPEG at 60 fps could produce 20–40 MB/s | F5 (all storage mechanisms) | If the storage medium cannot sustain the required write bandwidth, buffering overflow will cause frame drops regardless of buffer strategy. Cheap SD cards are a known failure mode |
| U7 | **Is the eye camera's 60 fps stable over long durations, or does the actual rate fluctuate?** The scene camera tested at 29.96 fps (stable). The eye camera at 60 fps has not been verified for stability | F2, F3, F4 | Frame rate instability at the source invalidates assumptions about uniform inter-frame intervals and complicates timestamp alignment algorithms |
| U8 | **What is the actual frame-to-frame jitter distribution?** Mean FPS may be correct (30/60), but variance (jitter) determines whether individual timestamps are usable for gaze mapping | F3, latency analysis deliverable | High jitter (>2–3 ms standard deviation) would reduce the scientific value of the timestamp data and may require statistical compensation in downstream processing |

### 4.3 Exploratory Unknowns (Lower Impact, Future Relevance)

| ID | Unknown | Affected Mechanisms | Potential Impact |
|----|---------|---------------------|------------------|
| U9 | **Does the eye camera support external trigger or strobe input?** USB UVC cameras typically do not expose hardware trigger pins | F3 Mechanism C (hardware trigger) | If the current cameras lack trigger input, hardware synchronization is impossible without camera replacement |
| U10 | **What is the power consumption profile of the full pipeline under load?** Unknown current draw of cameras + embedded board during sustained capture | F2 Mechanism B (adaptive degradation), future wearable design | Exceeding battery budget would invalidate any deployment scenario without tethered power |
| U11 | **How does YUYV (uncompressed) capture compare to MJPEG for pupil detection accuracy?** YUYV avoids compression artifacts but is limited to much lower FPS (5–10 fps at full resolution) | F1, F2, downstream processing | If MJPEG artifacts degrade pupil detection, a lower FPS with YUYV might produce better overall results — this is an unexplored trade-off |
| U12 | **Is the USB device node assignment (`/dev/videoX`) stable across reboots?** Linux may reassign device numbers, breaking hardcoded paths | F1 (all mechanisms assume known device paths) | Non-deterministic device assignment would require udev rules or dynamic camera discovery logic |

---

## 5. Mechanism vs. Function Summary Matrix

The table below shows which mechanisms have been identified for each core function, mapped against feasibility with the current hardware.

| Core Function | Mechanism A | Mechanism B | Mechanism C | Mechanism D |
|---------------|-------------|-------------|-------------|-------------|
| **F1** Camera Interfacing | V4L2 Direct ✅ | GStreamer Framework ✅ | OpenCV Abstraction ✅ | MIPI CSI Direct ⚠️ |
| **F2** Frame Rate Mgmt | Static Config ✅ | Adaptive Scaling ⚠️ | Multi-Profile ✅ | — |
| **F3** Timestamping | Monotonic Clock ✅ | UVC Metadata ❓ | Hardware Trigger ❌ | PTP/NTP ❌ |
| **F4** Buffering | Ring Buffer ✅ | Unbounded Queue ⚠️ | V4L2 Kernel Buffers ✅ | — |
| **F5** Encoding & Storage | MJPEG Pass-Through ✅ | Hardware H.264 ⚠️ | Lossless Archival ⚠️ | Segmented Recording ✅ |
| **F6** Data Export | Wired USB/Ethernet ✅ | WiFi Transfer ⚠️ | BLE Metadata Only ✅ | Removable Media ✅ |

**Legend:**  
✅ Feasible with current hardware and environment  
⚠️ Feasible but requires validation, additional hardware, or future-phase implementation  
❓ Existence confirmed, validity unverified  
❌ Not feasible with current hardware

---

## 6. Key Research Questions Enabled by This Design Space

The design space naturally exposes several research-worthy questions aligned with the project's deliverables:

1. **Sampling Rate vs. Detection Accuracy:** How does eye camera FPS (30 vs. 60 Hz) affect pupil detection precision, saccade capture fidelity, and fixation identification reliability?

2. **Compression Artifact Impact:** Does MJPEG compression degrade pupil ellipse fitting compared to raw/YUYV frames, and if so, at what quality threshold does the degradation become significant?

3. **Software Timestamp Sufficiency:** Is `CLOCK_MONOTONIC` software timestamping (with its inherent jitter) sufficient for gaze-to-scene mapping at 60 Hz, or is UVC metadata-based timing required for acceptable accuracy?

4. **Thermal-Sustained Performance:** What is the maximum sustained capture duration before thermal throttling causes measurable frame drop rate increase, and how does this vary with encoding strategy (MJPEG pass-through vs. H.264 re-encode)?

5. **USB Bandwidth Contention:** Under dual-camera simultaneous MJPEG capture, what is the measured USB bus utilization, and does it approach saturation under worst-case (high scene detail) conditions?

---

---

## 7. Assumption to Mechanism Evaluation Matrix

This matrix evaluates the compatibility and performance of primary design mechanisms against the critical system assumptions. It serves as a decision-support tool for concept selection.

| Assumption ↓ / Mechanism → | F1-A: V4L2 Direct | F1-C: OpenCV | F3-A: Monotonic Clock | F3-B: UVC Metadata | F5-A: MJPEG Pass-Through | F5-B: Hardware H.264 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A1:** Dual USB UVC Cameras | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **A6:** USB Bandwidth Sufficient | ✓ | ✓ | ✓ | ⚠️ | ✓ | ✓ |
| **A11:** Ubuntu Linux Env | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **A13:** Soft Real-time Req | ✓ | x | ✓ | ⚠️ | ✓ | ⚠️ |
| **A15:** Mandatory Timestamps | ✓ | x | ✓ | ✓ | ✓ | ✓ |
| **A7:** Hardware Encoding Avail | ✓ | ✓ | ✓ | ✓ | ✓ | ⚠️ |
| **A8:** Sufficient Local Storage | ✓ | ✓ | ✓ | ✓ | ⚠️ | ✓ |

**Legend:**  
✓ **Compatible:** The mechanism directly supports or operates reliably under the assumption.  
x **Incompatible:** The mechanism violates the assumption or lacks necessary features.  
⚠️ **Conditional:** Functionality depends on external factors (e.g., driver support, specific hardware SKU) or introduces secondary risks.

### Matrix Insights:

1.  **OpenCV Limitation:** While excellent for prototyping, Mechanism F1-C (OpenCV) fails critical requirements for deterministic soft real-time capture (**A13**) and mandatory frame-level timestamping (**A15**) because it abstracts away low-level device state.
2.  **Storage vs. Encoding:** MJPEG Pass-Through (**F5-A**) is the most robust against encoding-related failures but introduces a risk for **A8** due to high bitrates. Conversely, H.264 (**F5-B**) relies heavily on the unvalidated assumption of hardware encoder availability (**A7**).
3.  **Timing Precision:** The Monotonic Clock approach (**F3-A**) is safe for development, but UVC Metadata (**F3-B**) is the only path that potentially satisfies the need for high-accuracy hardware timing, provided the unknown **U2** is resolved.

*This matrix will be updated as the "Critical Unknowns" (U1–U4) are resolved through empirical testing.*

