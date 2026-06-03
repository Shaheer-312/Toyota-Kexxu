# Toyota-Kexxu — 10-Week Industry Integration Master Plan
**Team Size:** 5 Members | **Platform:** Raspberry Pi 5 | **Context:** Toyota Engine IIL Inspection

---

## 1. Executive Summary
Toyota conducts ~150 vehicle inspections daily. Currently, defects are recorded manually on paper checksheets (Corolla/Yaris) with manual end-of-day summaries, lacking any dashboard visualization or objective verification of *where* the inspector looked. 

**The Goal:** Build an end-to-end wearable eye-tracking system (both leveraging the Kexxu prototype and designing a custom RPi 5-based prototype) that digitizes this workflow. The system will track the inspector's gaze, map it to the Engine IIL checklist components, and present the data on a cloud dashboard to modernize Toyota's QA process.

---

## 2. Standard of Documentation & Deliverables

### Standards of Documentation
All documentation must adhere to professional Systems Engineering standards:
* **Code:** Python PEP 8 standards with full docstrings.
* **CAD:** Version-controlled STEP/STL files with physical tolerance notes.
* **Research/Decisions:** Trade studies using Pugh Matrices (e.g., comparing camera sensors).
* **Toyota Context:** All testing scenarios must map directly to the provided `Corolla Engine Process IIL.xlsx` checklist.

### Required Deliverables
1. **Hardware:** Functional custom 3D-printed glasses frame with dual cameras (Eye + Scene).
2. **Embedded Software:** Robust RPi 5 capture pipeline (CSI/USB) saving MJPEG/CSV.
3. **Cloud/ML Pipeline:** Offline processing pipeline mapping gaze vectors to scene components.
4. **Web Dashboard:** UI displaying the 150 daily inspections, showing gaze heatmaps over engine bays.
5. **Verification Report:** Formal analysis of frame drops, jitter, and calibration slippage.

---

## 3. Team Roles & Responsibilities (5 Members)

| Member | Role | Core Responsibilities |
| :--- | :--- | :--- |
| **Member 1** | **CV/ML & Post-Processing** | Pupil detection algorithms (PuRe/CNN), 3D gaze vector estimation, cloud backend architecture (Docker/GCP). |
| **Member 2** | **Software & Dashboard** | Scene camera homography, Toyota checklist digitization, Web Dashboard development (FastAPI/React). |
| **Member 3** | **Hardware & CAD** | 3D modeling (Fusion360), camera/lens procurement, IR LED circuitry, kinematics (weight balance). |
| **Member 4** | **Verification & QA** | Jitter analysis, synchronization testing, endurance testing, mapping tests to Toyota's Engine IIL sheet. |
| **Member 5** | **Embedded Systems Lead** | RPi 5 pipeline architecture, V4L2/libcamera interfacing, multiprocessing synchronization, storage formats. |

---

## 4. Learning Sets & Technical Research Areas

> [!IMPORTANT]
> Every team member must understand these concepts at a high level. Specialists will dive deep.

### L1: Interfaces — USB 3.0 vs. MIPI CSI-2
* **USB 3.0 Protocol:** Operates on *Isochronous transfers* for cameras (guaranteeing bandwidth but not delivery). The 80% rule means only 80% of bus bandwidth can be reserved. 
* **The Problem:** Plugging two high-res USB UVC cameras into the same controller causes bandwidth saturation (the bug seen in the Kexxu prototype).
* **Ideal Interface (MIPI CSI-2):** The RPi 5 features dual 4-lane MIPI CSI-2 ports. This is a direct hardware interface (DMA) that bypasses the USB controller entirely, offering zero latency and no bandwidth contention. *Your custom prototype must use CSI.*

### L2: Data Formats for Scientific Capture
* **MJPEG (Recommended for Capture):** Each frame is an independent JPEG. It is computationally free (compressed by the camera hardware) and perfectly frame-accurate/seekable for CV processing.
* **H.264/H.265 (For Archival):** Highly compressed but relies on keyframes (GOP). Terrible for frame-by-frame scientific analysis unless decoded first. 
* **CSV:** The lightest, fastest way to record timestamp metadata (`CLOCK_MONOTONIC`).

### L3: CV vs. ML for Pupil Detection
* **Traditional CV (e.g., PuRe, ExCuSe):** Uses edge detection and ellipse fitting. **Pros:** Extremely fast (runs on RPi 5 at 60fps), requires no training data. **Cons:** Fails in bad lighting or high reflection.
* **Machine Learning (e.g., DeepGaze, YOLO-Iris):** Uses CNNs. **Pros:** Highly robust to "in-the-wild" Toyota factory lighting. **Cons:** Requires a GPU for fast processing and large labeled datasets.
* **Approach:** Capture locally on the RPi 5. Process offline using Cloud ML to map the pupil.

### L4: Hardware Kinematics & Ergonomics
* **The Slippage Problem:** If the glasses move >2mm on the user's face (due to weight or looking down at an engine), the calibration is ruined.
* **Kinematics:** The center of mass must rest on the bridge of the nose. Avoid heavy processing units on the head (decoupled architecture: cameras on face, RPi 5 on belt).

### L5: Cloud Post-Computing Infrastructure
* **What Cloud?** Use **Vast.ai** or **RunPod** for budget-friendly GPU instances (A100s for ~$0.30/hr) during development. For final deployment, use **Google Cloud (GCP)** or **AWS** for enterprise security (important for Toyota).
* **VM vs. Container:** Do not use raw VMs. Use **Docker Containers**. Build a container containing your ML pipeline, push the recorded data from the RPi 5 to the cloud, spin up the container, process the heatmaps, and send results to the dashboard.

---

## 5. Day-by-Day 10-Week Master Plan

### Week 1: Project Kickoff, Setup & Core Research
* **Day 1:** Team kickoff. Review Toyota checksheets. Setup Git repository and Slack/Discord.
* **Day 2:** Flash 5x Raspberry Pi 5s with OS Bookworm. Establish SSH access and Python `.venv`.
* **Day 3:** **Learning Day:** Team reviews USB 3.0 vs CSI architecture and V4L2 documentation.
* **Day 4:** Run existing Kexxu `capture_pipeline.py`. Identify frame drop issues (Member 5).
* **Day 5:** Hardware team (Member 3) identifies CSI global shutter cameras (e.g., OV9281) and orders them.

### Week 2: Deep Dives & Software Skeletons
* **Day 1:** M1 & M2 research PuRe algorithm vs CNN approaches. Pull OpenCV examples.
* **Day 2:** M2 starts FastAPI skeleton for the Web Dashboard. M1 sets up Docker base image.
* **Day 3:** M5 re-writes the capture pipeline to support `libcamera` (for upcoming CSI cameras).
* **Day 4:** M3 begins Fusion360 CAD modeling of the base glasses frame (using safety glasses reference).
* **Day 5:** M4 writes the Verification Test Plan (VTP) based on Toyota's engine checklist.

### Week 3: Hardware Arrival & Initial Integration
* **Day 1:** CSI cameras arrive. M3 & M5 connect them to the RPi 5 and attempt single stream capture.
* **Day 2:** M5 attempts *dual* simultaneous CSI stream capture using `Picamera2` or `libcamera`.
* **Day 3:** M1 writes python script to extract frames from `.mkv` and run basic pupil contour detection.
* **Day 4:** M2 digitizes the Toyota `Corolla Engine Process IIL` into a JSON database for the dashboard.
* **Day 5:** M3 prints first 3D CAD prototype (V1). Test physical fit and kinematics on team.

### Week 4: Pipeline Connectivity & IR Illumination
* **Day 1:** M3 designs IR LED circuit (850nm, GPIO driven).
* **Day 2:** M5 integrates timestamping (`CLOCK_MONOTONIC`) into the dual CSI pipeline.
* **Day 3:** M1 & M2 attempt to map a detected pupil coordinate to a 3D gaze vector (math modeling).
* **Day 4:** M4 runs first jitter analysis on the timestamps produced by the CSI pipeline.
* **Day 5:** Assemble V1 glasses: Mount cameras and IR LEDs to 3D printed frame.

### Week 5: Core Processing & Toyota Context
* **Day 1:** Full capture test with V1 glasses. User wears them and looks at a mock engine bay.
* **Day 2:** M1 processes the mock data on the cloud. Does the ML algorithm detect the pupil?
* **Day 3:** M2 implements 9-point calibration logic (user looks at 9 points to create a homography matrix).
* **Day 4:** M3 refines CAD based on slippage (V2). Iteration on nose-pad grip and center of gravity.
* **Day 5:** M4 verifies the calibration accuracy (how many degrees of error?).

### Week 6: Cloud Integration & Dashboard Alpha
* **Day 1:** M1 deploys the processing pipeline to a GPU instance on Vast.ai / RunPod.
* **Day 2:** M5 writes an automated rsync script to push session data from RPi 5 SSD to the cloud.
* **Day 3:** M2 builds the frontend Dashboard UI (React/HTML). Shows a list of "Completed Inspections".
* **Day 4:** M2 integrates the Toyota defect checklist into the UI (simulating the paper process).
* **Day 5:** End-to-end data test: RPi 5 captures → Uploads to Cloud → Processed → Displayed on Dashboard.

### Week 7: Gaze Mapping & Feature Extraction
* **Day 1:** M2 & M1 work on Scene Mapping: Overlaying the gaze vector onto the 1080p front camera video.
* **Day 2:** Heatmap generation: M1 uses KDE (Kernel Density Estimation) to generate heatmaps of gaze.
* **Day 3:** Print CAD V3 (Final). Route cables securely to avoid snagging during car inspections.
* **Day 4:** M4 runs a 30-minute endurance test to check RPi 5 thermal throttling.
* **Day 5:** Team Review: Compare the custom prototype vs. the Kexxu prototype side-by-side.

### Week 8: Toyota Scenario Simulation
* **Day 1:** Simulate a real Toyota inspection using the Corolla Engine IIL checksheet.
* **Day 2:** Process the inspection data. Ensure the dashboard clearly shows what parts the inspector looked at.
* **Day 3:** M2 refines dashboard UI for Toyota management (summarizing 150 daily inspections).
* **Day 4:** Fix any pipeline crashes, handle edge cases (e.g., user blinks, head moves too fast).
* **Day 5:** M4 validates that the frame timestamps between Eye and Scene cameras are perfectly synced.

### Week 9: Verification, Polish & Bug Squashing
* **Day 1:** M3 finalizes the Bill of Materials (BOM) and assembly instructions.
* **Day 2:** M5 cleans up the embedded C++/Python code, adds comments, standardizes PEP 8.
* **Day 3:** M1 & M2 optimize cloud processing speed (aiming to process a 5-min inspection in <2 mins).
* **Day 4:** M4 finalizes the Verification Report (quantifying accuracy, frame rate stability).
* **Day 5:** Freeze code. No new features.

### Week 10: Final Deliverables & Handover
* **Day 1:** Draft the Final Technical Report combining all trade studies and research.
* **Day 2:** Record a high-quality video demonstration of an engine inspection using the glasses.
* **Day 3:** Prepare the presentation slides for the university/Toyota stakeholders.
* **Day 4:** Package the codebase into a clean, open-source-style GitHub repository with a clear README.
* **Day 5:** Project Sign-off and Celebration.
