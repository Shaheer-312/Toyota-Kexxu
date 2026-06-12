# Proposed Standardized GitHub Repository Layout

To transition this project from a messy development space into a professional, collaborative GitHub repository, we should establish a clean directory structure. Below is the proposed layout, separating source code, documentation, configuration, and data.

---

## 📁 Proposed Repository Tree

```
toyota-kexxu-eyetracking/
├── .github/                  # GitHub specific workflows (CI/CD, PR templates)
│   └── workflows/
├── config/                   # System-level configuration files
│   ├── 99-kexxu-cameras.rules # Custom udev rules for camera symlinks
│   └── kexxu-dashboard.service # systemd service unit file for auto-start
├── data/                     # Local test data directory (GIT-IGNORED)
│   └── README.md             # Explains directory usage, but data files are ignored
├── docs/                     # Design, setup, and verification documentation
│   ├── hardware/             # CAD models (STEP/STL), BOM, schematics
│   ├── setup/                # Environment setup guides, SOPs
│   └── verification/         # Verification plans (VTP), test reports, jitter logs
├── src/                      # Active production source code
│   ├── embedded/             # Raspberry Pi capture pipeline
│   │   ├── __init__.py
│   │   ├── capture_pipeline.py
│   │   ├── camera_backends.py # Abstraction for CSI vs. USB cameras
│   │   └── utils.py
│   ├── dashboard/            # FastAPI & HTMX Web Dashboard
│   │   ├── static/           # CSS, JS, Images
│   │   ├── templates/        # HTML templates (HTMX)
│   │   ├── __init__.py
│   │   └── main.py           # FastAPI entry point
│   └── post_processing/      # Offline analysis pipeline (Cloud/Desktop)
│       ├── __init__.py
│       ├── pupil_detection.py # PuRe / contour detection algorithms
│       ├── gaze_estimation.py # 3D vector & calibration homography mapping
│       └── heatmap_gen.py     # Gaze trace mapping & KDE heatmaps
├── .gitignore                # Rules for files that Git must ignore
├── LICENSE                   # Open-source license (e.g., MIT)
├── README.md                 # Project landing page (Quickstart, Team, Architecture)
└── requirements.txt          # Python dependency list
```

---

## 🔍 Directory Details

### 1. `src/` (Source Code)
We segment the codebase into three distinct modules to make the code easier to maintain and test:
*   **`src/embedded/`:** Holds code running on the Raspberry Pi 5 that controls physical cameras, manages thread/process queues, and saves raw videos and CSV timestamps to disk.
*   **`src/dashboard/`:** The local Web UI hosted on the Pi. Keep frontend assets (`static/`, `templates/`) grouped with the backend FastAPI code (`main.py`).
*   **`src/post_processing/`:** The heavy computer vision/machine learning pipeline. This can run either on a local developer machine or a cloud GPU container (Docker).

### 2. `docs/` (Documentation)
We eliminate vague folders like `Deliverables`, `Summers TSI`, or `Python Scripts` and consolidate everything under a structured `docs` folder:
*   **`docs/hardware/`:** Holds your Fusion360 STEP/STL exports, 3D printing parameters, component spec sheets, and electrical schematics for the IR LED drivers.
*   **`docs/setup/`:** Reproducibility guides for new developers or Toyota staff.
*   **`docs/verification/`:** The QA team’s domain. Test procedures, benchmark statistics, calibration error plots, and thermal profiling results.

### 3. `config/` (System Configs)
Centralizes system files that need to be copied to root directories during deployment (e.g., `/etc/udev/rules.d/` or `/etc/systemd/system/`).

### 4. `data/` (Crucial Git Practice)
> [!WARNING]
> Do NOT commit video files (`.mkv`) or large metadata CSVs to GitHub. Git is not designed to track large, changing binary files and doing so will quickly bloat the repository size.
*   The `data/` directory will serve as your local target for SSD recordings.
*   It is added to `.gitignore` so no raw session data is ever accidentally committed.

---

## 🛠️ Step-by-Step Transition Plan

To reorganize the folder without losing your git history, follow these steps in your terminal:

### Step 1: Initialize Requirements & Clean `.gitignore`
Write the current dependencies and create a clean gitignore that ignores data sessions:
```bash
# Capture dependencies
pip freeze > requirements.txt

# Create/Update .gitignore
cat << 'EOF' > .gitignore
.venv/
__pycache__/
*.pyc
data/
Toyota-Kexxu_Data/
.idea/
.vscode/
*.mkv
*.csv
EOF
```

### Step 2: Create Proposed Directories
```bash
mkdir -p config docs/hardware docs/setup docs/verification src/embedded src/dashboard src/post_processing data
```

### Step 3: Move Code and Docs (Preserving Git History)
Use `git mv` (instead of standard `mv`) so Git preserves the file history:
```bash
# Move capture pipeline into embedded source
git mv capture_pipeline.py src/embedded/

# Move udev and system setup details to setup docs
git mv linux_environment_setup.txt docs/setup/

# Move specs and SOPs into docs
git mv "Kexxu Prototype" docs/hardware/kexxu_prototype_specs
git mv Deliverables/ docs/deliverables_archive  # Keep as archive, clean up later
git mv "Summers TSI" docs/summers_tsi_archive  # Archive

# Commit the migration
git commit -m "refactor: reorganize repository structure to standard layout"
```
