# Toyota-Kexxu FYP Tasks

## Phase 1: Foundation (Weeks 1-3)

### Week 1: Project Kickoff, Setup & Core Research
- [ ] **Day 1: Project Initiation**
  - [ ] Review Toyota Corolla/Yaris engine checksheets
  - [ ] Set up monorepo and Git branching strategy (`main`, `dev`, feature branches)
  - [ ] Create Slack/Discord team communication channels
- [ ] **Day 2: Raspberry Pi 5 Infrastructure**
  - [ ] Flash 5x Raspberry Pi 5s with Raspberry Pi OS Bookworm
  - [ ] Establish SSH access and secure credentials
  - [ ] Initialize Python `.venv` and install base dependencies (numpy, linuxpy)
- [ ] **Day 3: Learning & Architecture**
  - [ ] Team review session: USB 3.0 protocol vs MIPI CSI-2
  - [ ] Team review session: V4L2 and libcamera documentation
- [ ] **Day 4: Existing Pipeline Validation**
  - [ ] Run Kexxu `capture_pipeline.py` on RPi 5
  - [ ] Identify and document frame drop issues (Member 5)
- [ ] **Day 5: Hardware Procurement**
  - [ ] Member 3: Identify ideal CSI global shutter cameras (e.g., OV9281)
  - [ ] Order custom CSI cameras and necessary 22-pin ribbon cables

### Week 2: Deep Dives & Software Skeletons
- [ ] Research PuRe algorithm vs CNN pupil detection approaches
- [ ] Create FastAPI backend skeleton for the Web Dashboard
- [ ] Set up Docker base image for Cloud ML processing
- [ ] Adapt `capture_pipeline.py` to support `libcamera` for future CSI integration
- [ ] Start Fusion360 CAD modeling of the base glasses frame
- [ ] Draft the formal Verification Test Plan (VTP) based on Toyota checklists

### Week 3: Hardware Arrival & Initial Integration
- [ ] Connect CSI cameras to RPi 5 and attempt single stream capture
- [ ] Implement dual simultaneous CSI stream capture
- [ ] Write Python script for frame extraction and basic pupil contour detection
- [ ] Digitize Toyota Corolla Engine Process IIL into JSON database
- [ ] Print first 3D CAD prototype (V1) and test physical fit

## Phase 2: Hardware Prototype (Weeks 4-6)
- [ ] To be populated

## Phase 3: Post-Processing & Cloud (Weeks 7-8)
- [ ] To be populated

## Phase 4: Integration & Validation (Weeks 9-10)
- [ ] To be populated
