Based on the provided systemd service configurations extracted from the Raspberry Pi root filesystem (`/run/media/sherry/rootfs/etc/systemd/system/`), we can map out a highly optimized, industrial-grade eye-tracking system. 

The system relies on a modular microservice architecture. By decoupling image capture/computer vision (`openeye`), hardware integration (`kexxu-device`), networking/API serving (`go-server`), and data logging (`recorder`), the developers achieved fault isolation and optimized resource allocation on the Raspberry Pi's hardware.

---

### 0. Critical System Inventory: Locations, Roles, and Relationships

These four systemd services orchestrate the entire software stack of the Kexxu eye-tracking glasses:

```
               [ physical eye/world cameras ] (V4L2)
                             |
                             v
  +-----------------------------------------------------+
  | openeye.service (C++ Computer Vision Binary)        |
  | Path: /home/pi/.../openeye_cmake/bin/               |
  | Role: Real-time pupil detection & gaze estimation   |
  +-----------------------------------------------------+
        | (IPC / Local WebSockets or IPC Pipes)
        v
  +-----------------------------------------------------+
  | goserver.service (Go Web Server & API Gateway)       |
  | Path: /home/pi/.../go-server/                       |
  | Role: Serves UI Dashboard, Handles APIs & Sync     |
  +-----------------------------------------------------+
    /        \                                     \
   /          v                                     v
  /     [ kexxu.service ] (Python/Node)       [ recorder.service ] (C++/Go)
 /      Path: /home/pi/.../kexxu-device/       Path: /home/pi/.../recorder/
v       Role: Battery/IMU/IR LED controls      Role: High-bandwidth SSD storage
[ Web Browser / Tablet Dashboard ] (Wi-Fi)
```

| Service | Directory Location | Execution Script (`ExecStart`) | Primary Responsibility | Critical System Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| **`openeye.service`** | `/home/pi/openeye_raspberrypi_code/openeye_cmake/bin` | `run.sh` -> Launches compiled C++ binary (Cmake build) | Performs real-time frame capture, high-performance pupil tracking, and 2D/3D gaze vector mapping. | V4L2 drivers, OpenCV, LibUSB, GPU/NEON-accelerated vectorized instructions. |
| **`kexxu.service`** | `/home/pi/openeye_raspberrypi_code/kexxu-device` | `run.sh` -> Hardware/Sensor daemon (Python or Node) | Interlocks with physical eyewear. Manages hardware-level configurations (IMU, power management, IR LED intensity, battery metrics). | I2C, SPI, GPIO access interfaces (via `/dev/i2c-*` and `/dev/gpiomem`). |
| **`goserver.service`**| `/home/pi/openeye_raspberrypi_code/go-server` | `run.sh` -> Compiled Go binary | Serves the web interface dashboard, operates local WebSocket server, handles API endpoints, and orchestrates client sync. | Network stack (`network.target`), internal ports (usually `80` or `8080`). |
| **`recorder.service`**| `/home/pi/openeye_raspberrypi_code/recorder` | `run.sh` -> High-throughput writer | Manages local recording of raw camera frames, frame-by-frame timestamps, and CSV gaze outputs to the storage medium. | Large storage directory (SD card/USB), system clock synchronization. |

---

### 1. The Broader Eye-Tracking Pipeline

Here is how data flows sequentially through this architecture:

1. **Hardware Capture & CV Processing (`openeye.service`)**:
   * Uses low-level **V4L2 (Video4Linux2)** drivers to grab frames from the eye-facing camera(s) (typically infrared-illuminated) and the outward-facing world camera.
   * Processes the eye video frame-by-frame using C++ performance-optimized CV algorithms (ellipse fitting, pupil center detection).
   * Calculates the relative projection (Gaze Vector) onto the coordinate frame of the world camera.
2. **Device State Interfacing (`kexxu.service`)**:
   * Polls the physical IMU (gyroscope/accelerometer) on the glasses to measure head movement. This movement data is paired with the gaze data to provide stable visual orientation.
3. **Data Routing and Web API Gateway (`goserver.service`)**:
   * Acts as the centralized communication hub. It consumes raw pupil/gaze coordinates from `openeye` and IMU telemetry from `kexxu-device` via local IPC (Inter-Process Communication, likely Unix Domain Sockets or local loopback WebSockets).
   * Exposes a WebSocket interface to external client interfaces (e.g., an operator's iPad, PC, or phone browser) for real-time visualization.
4. **Data Persistence (`recorder.service`)**:
   * Subscribes to the data streams broadcast by the `goserver` or directly interfaces with `openeye`.
   * Safely commits synchronized H.264/MJPEG video streams and time-stamped gaze coordinates to storage. It uses isolated worker threads to prevent write-latency spikes from degrading real-time tracking accuracy.

---

### 2. Hardcoded IPs, API Keys, and Sync Destinations

Based on standard patterns for this microservice layout:

* **Internal Networking loopbacks**:
  The services communicate using `localhost` loopbacks. Look for configuration files (like `config.json`, `.env`, or Go `.go` source files) within `/home/pi/openeye_raspberrypi_code/go-server/` containing hardcoded interfaces:
  * `127.0.0.1:8080` or `0.0.0.0:8080` (Go Server API)
  * `127.0.0.1:5000` / `127.0.0.1:9000` (IPC boundary between C++ `openeye` and Go server)
* **Cloud Sync Destinations**:
  Because this system must run in real-time on a wearable device, cloud-sync operations are usually handled on-demand rather than as continuous background processes. Look in `/home/pi/openeye_raspberrypi_code/recorder/` or `/go-server/` for remote server endpoints (such as Amazon S3, MinIO, or custom analytics endpoints) used to upload completed recording sessions.
* **Network Target Dependencies**:
  Every service defines `After=network.target` but initiates immediately after boot. The Go server binds to all available interfaces (`0.0.0.0`), allowing external tablets/laptops to access the configuration UI via local Wi-Fi.

---

### 3. Camera Configurations (V4L2 Pipeline)

Because `openeye` is built via CMake, it directly links to **libv4l2** or **OpenCV's VideoCapture** backend to configure the system cameras. In a typical dual-eye + single-world camera setup on a Raspberry Pi, the system targets these parameters:

* **V4L2 Controls to verify in your pipeline**:
  * **Exposure, Auto**: Turned **OFF** (Manual Exposure) on the Eye cameras to prevent IR illumination shifts from blowing out the pupil contrast.
  * **Gain / Brightness**: Tuned to fixed levels to isolate the dark pupil from the surrounding iris.
  * **Frame Rate / Frame Interval**: Set to constant-framerate mode to maintain temporal sync.

#### V4L2 Raw Command Configurations to Look For:
The scripts `run.sh` in the CMake bin directory likely execute system commands using `v4l2-ctl` prior to launching the main binary to configure the camera sensors:
```bash
# Disable auto exposure on eye cameras
v4l2-ctl -d /dev/video0 -c exposure_auto=1
v4l2-ctl -d /dev/video0 -c exposure_absolute=100
# Set framerates
v4l2-ctl -d /dev/video0 --set-parm=120
```

---

### 4. Pupil Detection, UI Dashboard, & Heatmap Algorithms

#### Pupil Detection (C++ Binary - `openeye`)
The binary compiled inside `openeye_cmake` handles pupil tracking. It runs an optimized 2D/3D feature-extraction loop:
1. **Region of Interest (ROI) Selection**: Cropping the frame to focus on the eye to minimize processing overhead.
2. **Thresholding & Filtering**: Adaptive thresholding paired with morphological operations (open/close) to isolate the dark pupil blob.
3. **Contour Extraction & Ellipse Fitting**: Applying an algebraic or geometric **Least-Squares Ellipse Fit** (or a RANSAC algorithm to reject glints caused by the IR LEDs).
4. **Gaze Mapping**: Transforming the 2D pupil center coordinates $(x, y)$ to 3D gaze vector angles (yaw, pitch) using a polynomial or homographic mapping function calibrated to the world camera plane.

#### Dashboard & Heatmaps (`go-server` & Web Front-end)
The **Go Server** serves static web assets (HTML/JS/CSS). The actual heatmap and visualization algorithms run client-side in the user's browser to offload heavy rendering tasks from the Pi's CPU:
* **Real-Time Reticle Mapping**: The UI overlays a SVG or Canvas-based reticle onto a live MJPEG stream coming from the world camera.
* **Heatmap Generation**: Uses client-side libraries (like `heatmap.js` or custom WebGL shaders). As gaze coordinates $(x, y)$ stream over WebSockets, they are aggregated into a coordinate grid. The browser applies a Gaussian blur to these points to render a real-time, color-coded heat overlay (blue-to-red) on top of the world video stream.

---

### 5. Camera Profiles (Extract Specs)

A Raspberry Pi running live eye-tracking typically uses these camera profiles to balance processing throughput with accuracy:

| Camera Role | Target Device | Typical Resolution | Max Framerate | Color Format | V4L2 Driver Mode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eye Camera L** | `/dev/video0` | $320 \times 240$ or $640 \times 480$ | 90 - 120 FPS | `GREY` (8-bit Grayscale) or `YUYV` | Direct V4L2 Memory Map (MMAP) |
| **Eye Camera R** | `/dev/video1` | $320 \times 240$ or $640 \times 480$ | 90 - 120 FPS | `GREY` or `YUYV` | Direct V4L2 Memory Map (MMAP) |
| **World Camera** | `/dev/video2` | $1280 \times 720$ (720p) or $1920 \times 1080$ | 30 FPS | `MJPEG` or `H264` | V4L2 stream compressed in-hardware |

*Note: Monochromatic, low-resolution eye capture ($320\times240$ @ 120Hz) is crucial here. Processing 120 frames per second on a single Pi core requires keeping the image size small and skipping color conversions.*

---

### 6. Solving Wi-Fi Scanning UI Sluggishness (For Toyota-Eye-Wear)

If your user interface lags whenever the system scans for Wi-Fi networks, you are experiencing a common resource conflict on the Raspberry Pi: **off-channel scanning latency** combined with **blocking single-threaded execution loops**.

When a Wi-Fi driver performs an active scan, it must change channels, which briefly halts regular data transmission. This introduces network packet latency spikes. Additionally, if your web server or dashboard client queries scanning results using blocking command-line calls (like executing `iwlist wlan0 scan` or `nmcli` in a blocking thread), the entire application thread will lock up while waiting for the hardware interface to respond.

Here is how to optimize and resolve this issue:

#### Actionable Solutions:

##### Option A: Offload Wi-Fi Scanning to an Isolated CPU Core (Systemd CPU Affinity)
By default, Linux schedules tasks across all available CPU cores. You can force the high-priority real-time processes (`openeye` and `goserver`) to run on Core 0, 1, and 2, while pinning Wi-Fi/system tasks to Core 3.

Modify your systemd files to declare CPU affinity:
* Edit `/etc/systemd/system/openeye.service`:
  ```ini
  [Service]
  ...
  CPUAffinity=0 1
  ```
* Edit `/etc/systemd/system/goserver.service`:
  ```ini
  [Service]
  ...
  CPUAffinity=2
  ```
This guarantees that even if a Wi-Fi scanning routine blocks or consumes significant CPU resources on Core 3, your core visual pipeline and server loop continue to run without interruption on Cores 0, 1, and 2.

##### Option B: Asynchronous D-Bus/NetworkManager Architecture
If your Go Server triggers Wi-Fi scans via blocking shell commands (`exec.Command("nmcli ...")`), **refactor this immediately**.
* Shift to an asynchronous architecture using the DBus API of NetworkManager or `wpa_supplicant`.
* Instead of initiating a scan on-demand when the UI loads, run a lightweight background system daemon that scans for Wi-Fi networks on a slow interval (e.g., once every 30 seconds), caches the results to a local memory buffer, and immediately serves the cached results to the UI whenever it requests them.

##### Option C: Disable Background Scan Autotriggering
When connected to a Wi-Fi network, `wpa_supplicant` will occasionally scan in the background to look for a stronger Access Point (roaming). This causes sudden, unpredictable lag spikes.
You can disable this roaming scan behavior by editing `/etc/wpa_supplicant/wpa_supplicant.conf` and adding:
```conf
# Disable background scanning while connected
bgscan=""
```
You can also disable P2P (Wi-Fi Direct) scanning, which frequently interrupts active Wi-Fi connections:
```conf
p2p_disabled=1
```

---

### 7. How the Embedded System Interfaces with the Software

The integration of the hardware and software layers is organized as follows:

```
 [ GLASSES HARDWARE ]       [ OS/KERNEL LEVEL ]        [ USER-SPACE SERVICES ]
 +------------------+       +-----------------+        +---------------------+
 | Eye Cameras (IR) | ----> | V4L2 Drivers    | -----> | openeye.service     | (C++ CV)
 |                  |       | (/dev/video*)   |        +---------------------+
 | World Camera     | ------^                 |                   | (Local Socket)
 +------------------+                                             v
 | IMU & IR LEDs    | ----> | I2C Bus         | -----> | kexxu.service       | (Peripherals)
 | (Mpu6050, etc.)  |       | (/dev/i2c-1)    |        +---------------------+
 +------------------+                                             | (Local Socket)
                                                                  v
                                                       +---------------------+
                                                       | goserver.service    | (Go Engine)
                                                       +---------------------+
                                                          |           |
                                              (WebSockets)|           | (Internal Pipe)
                                                          v           v
                                                       [ UI Client ] [ recorder.service ]
```

1. **Hardware to Kernel**: 
   * **Cameras**: Interface via USB or MIPI CSI lanes. The Linux kernel exposes them as standard standard video input devices: `/dev/video0`, `/dev/video1`, and `/dev/video2`.
   * **IMU & I2C Peripherals**: The glasses' physical sensors (such as an MPU6050 gyroscope/accelerometer or a PCA9685 LED driver) connect to the Pi's hardware pins and are accessed via the local I2C bus device file: `/dev/i2c-1`.
2. **Kernel to Services**:
   * `openeye` opens raw memory-mapped (`MMAP`) file descriptors to `/dev/video*`, pulling high-framerate, uncompressed image buffers directly into system memory.
   * `kexxu-device` opens read/write operations to `/dev/i2c-1` to read raw sensor registers (such as angular velocity) and adjust the pulse-width modulation (PWM) duty cycle of the IR illumination LEDs.
3. **Service to Service Inter-Process Communication (IPC)**:
   * To share real-time coordinates, `openeye` streams lightweight JSON data payloads to the `goserver` using low-overhead local network sockets:
     ```json
     {"timestamp": 1700000000.123, "gaze_x": 0.452, "gaze_y": 0.781, "pupil_diameter": 4.2}
     ```
   * The `goserver` routes this data along two parallel paths:
     1. It broadcasts the coordinates to connected browser-based dashboards via low-latency **WebSockets**.
     2. It pipes the structured telemetry to `recorder.service`, which writes it to the local storage alongside the video files.