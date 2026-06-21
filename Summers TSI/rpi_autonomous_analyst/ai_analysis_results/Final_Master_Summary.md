# Master Architecture Document: Kexxu Wearable Eye-Tracking Platform (Raspberry Pi System)

---

## System Overview & File Inventory

The Kexxu system operates on a dual-pathway architecture: a high-performance, source-compiled **C++ engine** manages real-time computer vision, hardware-accelerated video capture, and high-frequency gaze calculations. A **Python/Go orchestration layer** handles cloud synchronization, telemetry logging, local networking, physical peripheral integration, and user-facing dashboards.

```
                                  [ KEXXU SYSTEM ARCHITECTURE ]
                                                │
         ┌──────────────────────────────────────┴──────────────────────────────────────┐
         ▼                                                                             ▼
[ NATIVE C++ PROCESSING PLANE ]                                         [ ORCHESTRATION & TELEMETRY PLANE ]
  - openeye C++ Engine                                                    - kexxu_device.py Core Daemon
  - Custom Compiled OpenCV 4.5.3-dev                                      - Go Web/Socket Server (go-server)
  - V4L2 Low-Level Driver Wrapper                                         - Python Telemetry & Cloud Clients
  - TensorFlow Lite Runtime                                               - Systemd Microservice Mesh
```

### System File & Directory Topography

```
/home/pi/
├── conf                              <-- Master system environment variables (IPs, credentials, serial configs)
├── openeye_raspberrypi_code/         <-- Physical target directory on disk
│   ├── enable_i2c_vc.sh              <-- Enables VideoCore (GPU) I2C interface (physical pins 27 & 28)
│   ├── script_install.py             <-- Installer dependency runner stub
│   ├── go-server/                    <-- Spawns the web server and WebSocket APIs
│   │   ├── run.sh                    <-- Startup script setting port bindings
│   │   └── go-server-raspberry       <-- Compiled Go binary (serves on-device UI dashboard)
│   ├── lsl-pipe/                     <-- Lab Streaming Layer (LSL) network bridge
│   │   ├── lsl-pipe.py               <-- Reads raw gaze values from Shared Memory IPC
│   │   └── openeye_out               <-- Symlink pointing to /dev/shm/openeye_out FIFO
│   ├── start/                        <-- Daemon launch scripts
│   │   ├── start-kexxu-device.sh     <-- Script to launch Python device state machine
│   │   ├── start-tf-eyetrack.sh      <-- Script to launch C++/TensorFlow Lite engine
│   │   └── start-scene-cam.sh        <-- Script to launch local MJPEG stream server
│   ├── recorder/                     <-- Telemetry, GPS, audio, and video capture sub-system
│   │   ├── run.sh                    <-- Shell wrapper setting up environment bindings
│   │   ├── recorder.py               <-- Coordinates video encodings, audio feeds, and GPS
│   │   └── ffmpeg                    <-- Statically linked FFmpeg binary optimized for ARM NEON/V4L2
│   ├── utils/                        <-- Image processing helper scripts
│   │   ├── mat2tensor.h              <-- Zero-copy C++ OpenCV-to-TensorFlow memory mapping header
│   │   ├── mipi_raw10_to_jpg.py      <-- Demuxer for 10-bit raw MIPI CSI-2 camera data
│   │   └── mono_to_jpg.py            <-- Grayscale converter for raw 8-bit IR eye cameras
│   ├── systemd/                      <-- Unit deployment files (Note: contains critical misspelled path)
│   │   ├── tf-eyetrack.service       <-- Service for real-time neural gaze calculations
│   │   ├── recorder.service          <-- Service for audio, video, and GPS logging
│   │   └── kexxu.service             <-- Service for system health, battery, and cloud sync
│   ├── wifi-cli/                     <-- Network provisioning interface
│   │   ├── install.sh                <-- Deploys CLI profiles to target binary path
│   │   ├── wifi-cli.py               <-- Interoperates with wpa_supplicant config
│   │   └── saved.json                <-- Fallback/provisioning SSID definitions
│   ├── scene-cam/                    <-- Local field-of-view streaming server
│   │   └── scene-cam.py              <-- MJPEG-over-HTTP web server streaming from /dev/video0
│   ├── openeye_cmake/                <-- Real-time gaze calculation build tree
│   │   ├── bin/                      <-- Native executable targets and run.sh script
│   │   └── src/                      <-- Core tracking implementations
│   │       ├── system_recorder.cpp   <-- Low-level C++ FIFO pipe writer
│   │       └── system_recorder.hpp   <-- C++ video stream output interfaces
│   └── kexxu-device/                 <-- Low-level physical control node
│       ├── kexxu_device.py           <-- Core Python device manager daemon
│       ├── run.sh                    <-- Startup script loading environment variables from /home/pi/conf
│       ├── tools_device.py           <-- System diagnostics wrapper (VCGenCMD hardware readings)
│       ├── tools_wifi.py             <-- Interoperability layer for wpa_supplicant
│       ├── client_action_http.py     <-- Cloud HTTP API sync interface
│       ├── client_mqtt_kexxu_device.py <-- Loopback MQTT telemetry broker wrapper
│       └── wpa_supplicant.conf       <-- Master wpa_supplicant profile settings
│
├── ai_cam/                           <-- Standalone eye camera validation test build
│   ├── src/
│   │   ├── system_aicam.cpp          <-- Native V4L2 capture and exposure loop (10-bit raw Y10)
│   │   ├── system_aicam.hpp          <-- Eye camera header definitions
│   │   └── main.cpp                  <-- Frame capture verification script
│   └── build/                        <-- Native compilation output path
│
├── test/
│   └── test.cpp                      <-- Test capture routine using basic OpenCV video interfaces
│
└── installation/                     <-- Built-from-source dependency trees
    └── OpenCV-master/                <-- Source-compiled OpenCV 4.5.3-dev
        ├── bin/
        │   └── setup_vars_opencv4.sh <-- Overrides default system libraries for OpenCV 4.5.3-dev
        ├── include/opencv4/opencv2/  <-- Core C++ mathematical header definitions
        │   ├── cvconfig.h            <-- Compile-time parameters (HAVE_EIGEN, HAVE_OPENCL, etc.)
        │   ├── calib3d/calib3d_c.h   <-- Levenberg-Marquardt optimizer definitions (CvLevMarq)
        │   ├── imgproc/imgproc_c.h   <-- Contour extraction and ellipse-fitting structures
        │   ├── flann/                <-- Approximate Nearest Neighbors search tree headers
        │   ├── videoio/              <-- Video capture drivers and properties
        │   └── highgui/              <-- Graphical output and event loop headers
        └── lib/
            └── python2.7/            <-- Shared object wrapper links (cv2.so)
```

### Systemd Microservice Mesh

System lifecycle events are managed through a decoupled systemd service mesh. High-priority, real-time image processing tasks are isolated from background networking and telemetry loggers.

```
          +-----------------------+      +-----------------------+
          |   tf-eyetrack.service |      |     kexxu.service     |
          |  (Tensorflow C++ RT)  |      |   (Device Manager)    |
          +-----------+-----------+      +-----------+-----------+
                      |                              |
                      v                              v
            /home/pi/openeye_.../          /home/pi/openeye_.../
            start-tf-eyetrack.sh           start-kexxu-device.sh
                      |                              |
                      +--------------+---------------+
                                     |
                                     v
                        +------------+------------+
                        |     recorder.service    |
                        |   (Telemetry/Capture)   |
                        +-------------------------+
```

#### Systemd Configuration Path Mismatch (System-Breaking Bug)

> [!WARNING]  
> There is a critical misspelling in the systemd configuration files.
>
> The physical directories on the disk are named:
> `/home/pi/openeye_raspberrypi_code/` (spelled **raspberry** with a `p`).
>
> However, the systemd configuration files (`tf-eyetrack.service`, `recorder.service`, and `kexxu.service`) reference:
> `/home/pi/openeye_rasberrypi_code/` (spelled **rasberry** without a `p`).
>
> On system boot, systemd will fail to locate the executable targets and error out with `File Not Found`.
>
> **The Fix:**
> Either correct the directory references in all three systemd service configurations, or run this command on the target system:
> `ln -s /home/pi/openeye_raspberrypi_code /home/pi/openeye_rasberrypi_code`

---

## End-to-End Eye-Tracking Pipeline Architecture

The tracking pipeline processes dual, high-frequency infrared camera feeds, filters out eyelashes and glare, fits an ellipse model, and projects a calculated gaze vector onto a real-time scene camera feed.

```
 [Eye-Camera Capture] ---> [ROI Cropper] ---> [Model 1 (Coarse Center)] ---> [Model 2 (Sub-pixel Center)] ---> [Geometric Gaze Mapping] ---> [MQTT/LSL Output]
```

### Step 1: Image Acquisition and Downsampling (`system_aicam_usb.cpp`)
* The system opens `/dev/video0` (an Omnivision OV9281 monochrome sensor) via Memory Mapped I/O buffers (`V4L2_MEMORY_MMAP`).
* It captures raw, compressed MJPEG frame buffers at 60Hz.
* It decodes these frames into an OpenCV structure: `imdecode(rawData, IMREAD_COLOR)`.
* To save memory and processing overhead, the system downsamples the image from 1280x800 to a flipped 640x400 monochrome image in a single loop step:

```cpp
for(y = 0; y < image.rows; y+=2){
    p1 = image.ptr<uchar>(y);
    p2 = image_grab.ptr<uchar>(y2);
    x2 = 640;
    for(x = 0; x < image.cols*3; x+=6){
       p2[x2] = static_cast<uchar>(p1[x]); 
       x2--; 
    }
    y2++;
}
```

### Step 2: Region of Interest (ROI) Cropping (`openeye.cpp`)
To minimize processing overhead, a localized region of interest is cropped out of `image_grab` using the config parameters `win_x`, `win_y`, and a bounding box size of 360x360 pixels:

```cpp
Mat crop = ai_cam_image( Range(conf.win_x, conf.win_x2), Range(conf.win_y, conf.win_y2) );
```

### Step 3: Coarse Pupil Center Detection (`openeye.cpp`)
* The 360x360 raw crop is resized to 90x90 pixels.
* The pixel values are normalized to a $[-0.5, 0.5]$ range:
  $$\text{Pixel}_{\text{norm}} = \frac{\text{Pixel}_{\text{raw}}}{256.0} - 0.5$$
* This normalized matrix is evaluated by **Model 1** (`pupil-4x-90.tflite`). The model outputs a probability distribution across 90 bins representing the $X$ and $Y$ axes. The system calculates the peak index to establish the coarse coordinates:
  $$\text{out\_x} \leftarrow \text{out\_x} + \text{conf.win\_y}$$
  $$\text{out\_y} \leftarrow \text{out\_y} + \text{conf.win\_x}$$

### Step 4: Sub-Pixel Target Optimization (`openeye.cpp`)
The coarse coordinates define the center of a high-precision 120x120 window cropped from the original image. This cropped image is fed to **Model 2** (`pupil-1x-120-v2.tflite`), which resolves the sub-pixel center offset:
$$\text{out\_x} = \text{crop\_x} + \text{offsets2\_x}$$
$$\text{out\_y} = \text{crop\_y} + \text{offsets2\_y}$$

### Step 5: Geometric Gaze Mapping (`openeye.cpp`)
The calculated pupil center coordinates are offset using the system calibration values:
$$\text{eye\_c\_x} = \text{conf.calibration\_center\_x} + (\text{out\_y} + \text{conf.win\_x})$$
$$\text{eye\_c\_y} = \text{conf.calibration\_center\_y} + (\text{out\_x} - \text{conf.win\_y})$$

Next, a multivariate regression polynomial maps these pupil coordinates ($x, y$) into coordinate vectors ($G_x, G_y$) relative to the perspective camera frame. This step corrects optical distortions and perspective skew:

$$G_x = c_{x\_x}x + c_{x\_y}y + c_{x\_xx}x^2 + c_{x\_xxx}x^3 + c_{x\_xxy}x^2y + c_{x\_xxyy}x^2y^2 + c_{x\_yy}y^2 + c_{x\_xyy}xy^2 + c_{x\_xy}xy$$

$$G_y = c_{y\_x}x + c_{y\_y}y + c_{y\_xx}x^2 + c_{y\_xxy}x^2y + c_{y\_xxyy}x^2y^2 + c_{y\_yy}y^2 + c_{y\_yyy}y^3 + c_{y\_xyy}xy^2 + c_{y\_xy}xy$$

### Step 6: Telemetry Broadcast (`openeye.cpp`)
* The calculated gaze points ($G_x, G_y$) are wrapped inside a JSON telemetry payload along with exact microsecond epoch timestamps.
* This telemetry payload is published via local loopback sockets to the local Mosquitto MQTT broker (`127.0.0.1:1883`) and streamed via the Lab Streaming Layer (LSL) network outlet interface.

---

## Network Topology, Security Audits, & Cloud Credentials

The Kexxu platform balances high-performance processing on the device with periodic data synchronization to its cloud backend.

```
                              [ NETWORK ARCHITECTURE DIAGRAM ]
                                              │
         ┌────────────────────────────────────┴────────────────────────────────────┐
         ▼                                                                         ▼
[ LOCAL TELEMETRY NETWORK ]                                               [ REMOTE CLOUD NETWORK ]
  - Mosquitto Broker (127.0.0.1:1883)                                       - VerneMQ Broker (vmq.kexxu.com:80)
  - Raw JSON Telemetry Broadcasts                                           - Cloud REST API (api.kexxu.com)
  - Zero-Copy RAMDisk writes (/dev/shm)                                     - Storage Uploads (18.192.205.32:3000)
```

### Static Configuration Matrix

| Resource Class | Key Identity | Value / Target Interface | Purpose |
| :--- | :--- | :--- | :--- |
| **Local MQTT Broker** | Loopback Host | `tcp://127.0.0.1:1883` | Direct internal messaging |
| **Local MQTT Credentials**| Dynamic ID | `"rec-" + KEXXU_DEVICE_ID` | Local client registration |
| **Local MQTT Login** | Static Username | `"kexxu"` | Local client login |
| **Local MQTT Password** | Static Password | `"vySgEjzJ524Er6PUaK6zKAKUe5MfAP"`| Local client access validation |
| **Remote MQTT Broker** | Cloud Endpoint | `tcp://vmq.kexxu.com:80` | Pushes device state events to cloud |
| **Remote MQTT Failback** | Legacy Host | `tcp://mqtt-1.kexxu.com:80` | Fallback cloud target |
| **Remote REST Endpoint** | Provisioning Host | `https://api.kexxu.com/api/device/action` | Telemetry & state syncing |
| **Remote API Query** | Action Target | `POST_ACTION_URL` query template | Handles device status registers |
| **Remote Config Query** | Info Target | `GET_WIFI_INFO_URL` query template | Fetches network profiles |
| **Remote Config Confirm**| AP Ack Target | `SET_WIFI_ACK_URL` query template | Verifies applied Wi-Fi changes |
| **Active Storage Endpoint**| S3-EC2 Gateway | `http://18.192.205.32:3000/api/{type}/upload` | Uploads raw recorded video sessions |

*Note: IP `18.192.205.32` points to an EC2 instance hosted in the AWS Frankfurt region (`eu-central-1`). This server acts as the primary telemetry collection endpoint.*

### Provisioning Wi-Fi Hotspots (`saved.json` / `wpa_supplicant.conf`)

The system uses three pre-configured Wi-Fi networks to handle initial provisioning and fallback support:

```json
{
  "saved": [
    { "ssid": "a_setup_hotspot", "passw": "setup_temporary" },
    { "ssid": "Pesky",           "passw": "Pesky2021!" },
    { "ssid": "test",            "passw": "12345678" }
  ]
}
```

*   `a_setup_hotspot` represents the default network used when first configuring a device.
*   Once connected, the system contacts `api.kexxu.com` using parameters passed via environment variables (`KEXXU_DEVICE_ID`, `KEXXU_DEVICE_PASSWORD`, `KEXXU_DEVICE_VERSION`), gets new local network profiles, updates `/etc/wpa_supplicant/wpa_supplicant.conf`, and restarts the connection.

---

## Hardware Ingestion & Camera Subsystems

The Kexxu system runs multiple concurrent video streams. To prevent saturating the Raspberry Pi's shared USB controller bus, the cameras are configured with distinct resolutions, framerates, and pixel formats:

```
                        +---------------------------------------+
                        |             VIDEO ENGINES             |
                        +---------------------------------------+
                                            |
                    +-----------------------+-----------------------+
                    |                                               |
                    v                                               v
        +-----------------------+                       +-----------------------+
        |   SystemAicamUsb      |                       |    SystemScenecam     |
        |   (Eye Tracker)       |                       |   (Perspective POV)   |
        +-----------------------+                       +-----------------------+
        |  * /dev/video0        |                       |  * /dev/video2        |
        |  * 1280x800           |                       |  * 1280x720           |
        |  * MJPEG Format       |                       |  * MJPEG Format       |
        |  * Target FPS: 60Hz   |                       |  * Target FPS: 60Hz   |
        +-----------------------+                       +-----------------------+
```

### Camera Configurations & V4L2 Control Profiles

#### Eye-Tracking Sensor (/dev/video0)
* **Sensor Model:** OmniVision OV9281 (Near-Infrared, Global Shutter)
* **Resolution:** 1280x800
* **Framerate:** 60 FPS
* **Pixel Format:** Native `V4L2_PIX_FMT_Y10` (10-bit raw grayscale), falling back to uncompressed `MJPEG`.
* **V4L2 Target Controls:**
  * **Analog Gain (`V4L2_CID_GAIN`):** Adjusted dynamically based on eye-tracking feedback. Bound to a $[0, 100]$ scale.

#### Wide-Angle Perspective Sensor (/dev/video2)
* **Sensor Model:** Sony IMX219 (Standard Visible Spectrum, Rolling Shutter)
* **Resolution:** 1280x720 (720p HD)
* **Framerate:** 60 FPS
* **Pixel Format:** Compressed `MJPEG`
* **V4L2 Target Controls:**
  * **Auto Exposure (`V4L2_CID_EXPOSURE_AUTO`):** Manually locked (`V4L2_EXPOSURE_MANUAL`) during calibrations to prevent shifts in ambient light from causing tracking errors.
  * **Shutter Speed (`V4L2_CID_EXPOSURE_ABSOLUTE`):** Set to a brief interval (value `10` register units) to prevent high-speed motion blur.

---

### Low-Level Capture Engine (`system_aicam.cpp`)

The low-level C++ capture engine accesses the camera sensors via V4L2 interfaces to ensure low-latency frame delivery.

```cpp
imageFormat.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
imageFormat.fmt.pix.width = 640;
imageFormat.fmt.pix.height = 480;
imageFormat.fmt.pix.pixelformat = V4L2_PIX_FMT_Y10;  // Raw 10-bit Grayscale
imageFormat.fmt.pix.field = V4L2_FIELD_NONE;         // Progressive scanning
```

High frame rates (120 FPS target) are requested directly via the driver parameters:

```cpp
struct v4l2_streamparm parm;
parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
parm.parm.capture.timeperframe.numerator = 1;
parm.parm.capture.timeperframe.denominator = 120;   // 120Hz Target
```

---

### Auto-Exposure Algorithm & Feedback Loop

The system runs a custom auto-exposure loop on every frame to maintain consistent image brightness under varying lighting conditions.

```
[Grab Frame] -> [Sample Grid (every 20th px)] -> [Mean Brightness] -> [Calculate Scale Factor] -> [V4L2 Exposure Adjustment]
```

```cpp
struct v4l2_control ai_cam_control;
ai_cam_control.id = V4L2_CID_EXPOSURE;
int n = 0;
double mean_brightness = 0.0;

// Subsampled grid check: reads every 20th pixel
for(int x = 0; x < 640; x += 20){
    for(int y = 0; y < 480; y += 20){
        mean_brightness += (double)(image.at<uchar>(y, x, 0));
        n++;
    }
}
mean_brightness /= (double)n;

// Calculate the feedback scale factor
float brightness_adj = 1 + (80 - mean_brightness) * 0.002;
cur_exposure *= brightness_adj;

// Clamping limits
if(cur_exposure > 1704){ cur_exposure = 1074; } // High-limit fallback
if(cur_exposure < 20){ cur_exposure = 20; }     // Low-limit clamp
```

#### Clamping Threshold Logic
* **Low Limit Clamp (`20`):** Prevents the exposure time from dropping to zero, which would cause the auto-exposure calculation to fail.
* **High Limit Clamp (`1704`) & Fallback (`1074`):** If the environment is very dark, the exposure value can escalate quickly. The high limit of `1704` protects the frame rate. If the exposure is set too high, the sensor cannot maintain its target frame rate of 120 FPS (where each frame must be captured in under 8.33 milliseconds). The immediate fallback to `1074` acts as a recovery state to keep the capture loop running.

---

### System Performance Bottlenecks & Critical Anomalies

#### Pixel Bit-Depth Mismatch (High Severity)
The C++ capture pipeline is configured to read the sensor in 10-bit raw grayscale (`V4L2_PIX_FMT_Y10`) and stores the frames in memory as 16-bit single-channel matrices:
```cpp
Mat image(Size(640, 480), CV_16UC1, buffer, Mat::AUTO_STEP);
```
However, the auto-exposure feedback loop reads pixel values as 8-bit unsigned characters:
```cpp
mean_brightness += (double)(image.at<uchar>(y, x, 0));
```
On little-endian architectures like the Raspberry Pi's ARM processor, reading a `CV_16UC1` pixel (which uses 2 bytes) as an 8-bit `uchar` (1 byte) reads only the least significant byte. This discards the most significant 2 bits of the 10-bit image data and corrupts the brightness calculation.

#### Under-Buffered Frame Queue (Medium Severity)
In `system_aicam.cpp`, the V4L2 driver is configured with a queue size of 1:
```cpp
requestBuffer.count = 1;
```
For high-speed real-time capture at 120 FPS, a queue size of 1 is highly prone to frame drops. If the CPU is busy running the main process or scanning for Wi-Fi networks, the single buffer cannot be cleared in time. This forces the camera sensor to drop frames. The system should use a circular buffer queue of at least **3 to 4 buffers** to prevent stuttering.

#### Frame Rate Mismatches (Medium Severity)
There is a frame rate mismatch between the C++ data writer and the Python reader:
* In `system_recorder.cpp`, the output is configured for **18 FPS**:
  ```cpp
  strcpy(newargv[8], "-r");
  strcpy(newargv[9], "18");
  ```
* In `recorder.py`, the dynamic queue launches FFmpeg configured for **21 FPS**:
  ```python
  "-r", "21"
  ```
This difference of 3 FPS between the C++ data writer and the Python/FFmpeg reader will cause **frame interpolation errors, audio-to-video sync drift, and constant underflow warnings** on the FIFO pipe during long recording sessions.

---

## C++ Computer Vision & Machine Learning Core

### Image-to-Tensor Conversion (`mat2tensor.h`)

To process frames through the TensorFlow models quickly, the system converts raw OpenCV frames (`cv::Mat`) into TensorFlow input tensors using a custom, zero-copy memory mapping method:

```cpp
tensorflow::Tensor Mat2Tensor(cv::Mat &img, float normal = 1/255.0) {
    tensorflow::Tensor image_input = tensorflow::Tensor(
        tensorflow::DT_FLOAT, 
        tensorflow::TensorShape({1, img.size().height, img.size().width, img.channels()})
    );

    float *tensor_data_ptr = image_input.flat<float>().data();
    cv::Mat fake_mat(img.rows, img.cols, CV_32FC(img.channels()), tensor_data_ptr);
    img.convertTo(fake_mat, CV_32FC(img.channels()));

    fake_mat *= normal; // Normalize pixels to [0.0, 1.0]

    return image_input;
}
```

This method is highly optimized:
* It allocates a TensorFlow `Tensor` with a batch size of `1`.
* It maps a custom OpenCV `cv::Mat` (`fake_mat`) **directly onto the underlying raw pointer of the TensorFlow tensor memory block**.
* Running `img.convertTo` writes the processed frame directly into TensorFlow's allocated memory, eliminating the need for an intermediate copy operation.

---

### Unpacking 10-Bit Raw MIPI CSI-2 Data

Low-cost infrared cameras often output raw 10-bit MIPI CSI-2 data. To save transmission bandwidth, the MIPI protocol packs four 10-bit pixels into 5-byte blocks:

```
Byte 1: [Pixel 0 High Bits (7-0)]
Byte 2: [Pixel 1 High Bits (7-0)]
Byte 3: [Pixel 2 High Bits (7-0)]
Byte 4: [Pixel 3 High Bits (7-0)]
Byte 5: [P3 Low (7-6) | P2 Low (5-4) | P1 Low (3-2) | P0 Low (1-0)]
```

The unpacking math is implemented as follows in `mipi_raw10_to_jpg.py`:

```python
def unpack_mipi_raw10(byte_buf):
    data = np.frombuffer(byte_buf, dtype=np.uint8)
    # Group every 5 bytes into 4 10-bit pixels
    b1, b2, b3, b4, b5 = np.reshape(data, (data.shape[0]//5, 5)).astype(np.uint16).T
    
    # Extract the high 8 bits and append the corresponding 2 bits from the 5th byte
    o1 = (b1 << 2) + ((b5) & 0x3)
    o2 = (b2 << 2) + ((b5 >> 2) & 0x3)
    o3 = (b3 << 2) + ((b5 >> 4) & 0x3)
    o4 = (b4 << 2) + ((b5 >> 6) & 0x3)
    
    unpacked = np.reshape(np.concatenate(
        (o1[:, None], o2[:, None], o3[:, None], o4[:, None]), axis=1),  4*o1.shape[0])
    return unpacked
```

Once unpacked, the script shifts the data 2 bits to the right (`img = img >> 2`) to downsample the 10-bit depth to standard 8-bit grayscale (`np.uint8`). This ensures compatibility with standard computer vision pipelines while preserving edge details.

---

### Calibration Point Detection & Visual Overlays

A calibration validation system overlays tracking coordinates onto the perspective scene frame. These overlays indicate whether calibration points (infrared beacons or red/blue targets) are detected.

```
       [IR Beacon Point]
            (  ) <--- White Spot Peak Detection
           /    \
   +------/------\------+
   |     /   *    \     |  <--- Green Bounding Frame (60px step check)
   |    *  Center  *    |
   |     \        /     |
   +------\------/------+
           \    /
            (  ) <--- Pink Symmetrical Validation Bounding Box (d=16px)
```

The validation system sweeps horizontal rows to detect point peaks based on light intensity levels:

```cpp
if(uint8_t(p[x])>201 && uint8_t(p[x+1])>201 && uint8_t(p[x+2])>201) { // GBR check
    found = true;
    marker_x = x_coordinate;
}
```

Symmetrical alignment checks verify the edges of the tracked points relative to the coordinate center:

```cpp
v1 = overlay_img.at<Vec3b>(y, x3-d, 0); // Left validation check
v2 = overlay_img.at<Vec3b>(y, x3+d, 0); // Right validation check
```

---

### Optimization Implementations inside FLANN and HAL

The system uses a custom compiled version of **OpenCV 4.5.3-dev** featuring several hardware optimizations:

```
[Raw Gaze Coordinates] ──> KD-Tree Search (kdtree_single_index.h) ──> [Neighbor Coordinates]
                                     │
                        KNN Weighting Interpolation
                                     │
                                     ▼
                        [Mapped Target Coordinate]
```

* **Vectorized Distance Calculations (`dist.h`):** Employs ARM NEON SIMD vector instructions to accelerate distance calculations (L1, L2, Hamming) when matching image features.
* **KD-Trees (`kdtree_single_index.h`):** Performs fast spatial indexing. At runtime, the mapped gaze target coordinate is calculated in real time by searching the closest calibration points.
* **Fixation Clustering (`kmeans_index.h`):** Groups spatial gaze points that are close to each other. This separates visual **fixations** (where the eye lingers) from fast movements (**saccades**) and is used to construct clean heatmaps.
* **Ellipse Fitting & Model Fitting (`simplex_downhill.h`):** Implements the Nelder-Mead simplex optimization algorithm. This derivative-free method is used to fit a 3D eyeball rotation matrix to minimize the error between the projected ellipse and the actual pixel contours.

---

## Resolving Wi-Fi Scanning UI Sluggishness (Toyota-Eye-Wear Fixes)

### The Root Cause of System Lag

The sluggishness in the user interface during Wi-Fi scanning is caused by two related issues: **thread blocking** and **radio channel hopping**.

```
[Main Thread] ---> [V4L2 Grab Frame] ---> [TFLite Inference] ---> [Blocking API / System Call] ---> [Mosquitto Network Flush] ---> [Loop Blocked]
                                                                          |
                                                      The loop stalls here while wpa_cli runs
```

1. **Kernel Driver Holds (WLAN Driver Lock):** The Raspberry Pi's Cypress/Broadcom Wi-Fi module shares its antenna and internal SDIO bus with the Bluetooth module.
2. **Off-Channel Dwell Time:** When a Wi-Fi scan is triggered (e.g., calling `iwlist wlan0 scan` or `wpa_cli reconfigure`), the wireless driver must leave its current channel and dwell on different channels to listen for beacon frames. This pauses active network transmissions.
3. **Local Socket Blocks:** Local communications (such as telemetry sent to the Go server) rely on TCP loopback connections. During a scan, these socket connections stall.
4. **Blocking System Calls:** The core orchestration code calls system commands synchronously:
   ```python
   # Inside tools_wifi.py (Blocks the main thread execution loop)
   out = subprocess.check_output(['iwgetid'])
   ```
   This causes the entire application to pause and wait for the hardware driver to finish scanning, resulting in visible lag and dropped frames in the UI.

---

### Actionable Solutions & Code Refactoring

To resolve the sluggishness, network tasks must be decoupled from the high-rate video processing loop.

```
[UI THREAD]            [SHARED MEMORY]           [DAEMON WORKER THREAD]     [HARDWARE]
     |                        |                            |                    |
     |--- Read Queue -------->|                            |                    |
     |    (Instant < 1ms)     |                            |                    |
     |                        |<-- Push Async Scan JSON ---|                    |
     |                        |    (Every 15-30s)          |                    |
     |                        |                            |--- Active Probe -->|
     |                        |                            |    (Blocks ~2s)    |
     |                        |                            |                    v
```

#### Fix 1: Non-Blocking, Asynchronous Wi-Fi Queries (DBus)
Instead of calling external system commands, we can query `wpa_supplicant` for cached scan results via the non-blocking **DBus system bus**. This allows us to retrieve nearby networks instantly without triggering a manual scan or blocking the thread.

```python
import dbus
import asyncio

async def get_cached_wifi_networks():
    try:
        bus = dbus.SystemBus()
        # Connect to wpa_supplicant DBus interface
        wpas_obj = bus.get_object('fi.w1.wpa_supplicant1', '/fi/w1/wpa_supplicant1')
        wpas = dbus.Interface(wpas_obj, 'fi.w1.wpa_supplicant1')
        
        # Get interface object for wlan0
        iface_path = wpas.GetInterface('wlan0')
        iface_obj = bus.get_object('fi.w1.wpa_supplicant1', iface_path)
        iface = dbus.Interface(iface_obj, 'fi.w1.wpa_supplicant1.Interface')
        
        # Pull cached BSSs (Basic Service Sets) - DOES NOT trigger an active scan
        bss_list = iface.Get('fi.w1.wpa_supplicant1.Interface', 'BSSs', dbus_interface='org.freedesktop.DBus.Properties')
        
        networks = []
        for bss_path in bss_list:
            bss_obj = bus.get_object('fi.w1.wpa_supplicant1', bss_path)
            bss_prop = dbus.Interface(bss_obj, 'org.freedesktop.DBus.Properties')
            
            # Extract SSID and Signal Strength (SSID is returned as a byte array)
            ssid_bytes = bss_prop.Get('fi.w1.wpa_supplicant1.BSS', 'SSID')
            ssid = "".join(chr(b) for b in ssid_bytes if 32 <= b < 127)
            rssi = bss_prop.Get('fi.w1.wpa_supplicant1.BSS', 'Rsync') # Signal level in dBm
            
            if ssid:
                networks.append({"ssid": ssid, "signal": int(rssi)})
        return networks
    except Exception as e:
        print(f"Non-blocking DBus Wi-Fi query failed: {e}")
        return []
```

#### Fix 2: CPU Pinning (Systemd CPU Affinity)
Configure the system to isolate core processes on different CPU cores. Pin the real-time C++ tracking modules to dedicated CPU cores, and assign all system and networking tasks to a separate core.

Modify your systemd configuration files:
* In `/etc/systemd/system/tf-eyetrack.service`:
  ```ini
  [Service]
  CPUAffinity=0 1 2   # Bind the eye-tracker to Cores 0, 1, and 2
  ```
* In `/etc/systemd/system/goserver.service` / Networking:
  ```ini
  [Service]
  CPUAffinity=3       # Force the web server and network tasks to Core 3
  ```

#### Fix 3: Disable Background Scans & Active Probes
Modify the host wireless configuration profiles in `/etc/wpa_supplicant/wpa_supplicant.conf` to stop background scanning when connected to a network:

```wpa_supplicant
ap_scan=1
# Stop scanning background frequencies while connected
bgscan="simple:20:-75:300"
p2p_disabled=1
```

#### Fix 4: Disable Wi-Fi Power Management
Raspberry Pi OS default power-saving features periodically put the Wi-Fi chip's receiver into a low-power sleep state, which spikes latency when the system receives frame packets. Disable this setting permanently by adding this to `/etc/rc.local`:

```bash
/sbin/iw dev wlan0 set power_save off
```

---

## Physical Hardware-to-Software Interconnection Architecture

```
       +-------------------------------------------------------------+
       |                  Raspberry Pi Hardware Host                 |
       +-------+--------------------+--------------------+-----------+
               |                    |                    |
  I2C (VC)     |       CSI-2        |        UART        |   ALSA
  Pins 27,28   |     Flex Cable     |     TTYAMA0        |   hw:2,0
               v                    v                    v           
       +-------+----+       +-------+----+       +-------+----+  +---+-------+
       | Camera /   |       | Eye Camera |       | GPS Unit   |  | Micro-    |
       | VC Sensor  |       | 10-Bit Raw |       | Telemetry  |  | phone     |
       +-------+----+       +-------+----+       +-------+----+  +---+-------+
               |                    |                    |           |
  i2c_vc       | Unpack raw         | NMEA sentences     | Raw Audio | Capture
  kernel driver| bayer frames       | /dev/ttyAMA0       | hw:2,0    | stream
               v                    v                    v           v
       +-------+----+       +-------+----+       +-------+----+  +---+-------+
       | enable_    |       | mipi_raw10_|       | recorder.py|  | recorder.py|
       | i2c_vc.sh  |       | to_jpg.py  |       | GPS Parser |  | Audio Thrd|
       +------------+       +------------+       +------------+  +-----------+
```

* **Camera Control Channel (I2C VC):**
  * **Hardware Interface:** Physical pins 27 and 28 (configured as the VideoCore I2C channel).
  * **Driver Mapping:** Enabled via `enable_i2c_vc.sh` (`dtparam=i2c_vc=on`). This allows the system to configure the camera module's internal registers directly (such as adjusting exposure, gain, and horizontal/vertical blanking).
* **High-Speed Gaze Input (CSI-2 Bus):**
  * **Hardware Interface:** 15-pin/22-pin FPC Flex Cable connector feeding raw frame data directly to the Broadcom ISP.
  * **Software Demuxing:** Managed by `mipi_raw10_to_jpg.py` to unpack raw MIPI patterns without dropping frames.
* **Telemetry and Localization Channel (UART):**
  * **Hardware Interface:** Raspberry Pi physical pins 8 and 10 (`TXD0` / `RXD0` mapped to serial interface `/dev/ttyAMA0`).
  * **Telemetry Parsing:** The core `recorder.py` service opens a serial connection at `9600 Baud` to read incoming NMEA GPS frames. It parses `$GNGGA` sentences on the fly and converts them into JSON objects to publish location updates.
* **Audio Capture (ALSA Hardware Bus):**
  * **Hardware Interface:** USB Microphone or external audio codec mapped to ALSA index card 2 (`hw:2,0`).
  * **Software Capture:** Spawns an independent FFmpeg recording instance to capture mono, 1-channel audio at $44.1\text{ kHz}$ to save synchronized sound files alongside the video data:
    ```bash
    ffmpeg -ar 44100 -ac 1 -f alsa -i hw:2,0 -fflags flush_packets output.mp3
    ```
* **Status Outputs (GPIO Pin 27):**
  * **Hardware Interface:** Physical Pin 13 (GPIO Pin 27).
  * **Software Integration:** The C++ code uses the `wiringPi` library to trigger an external buzzer for calibration confirmations and system alerts:
    ```cpp
    wiringPiSetup();
    pinMode(27, OUTPUT);
    digitalWrite(27, 1); // Triggers buzzer high
    ```

---

## Low-Latency Inter-Process Communication (RAMDisk Pipeline)

To maintain stable tracking and recording speeds, the system uses the virtual RAM filesystem `/dev/shm/` to share image frames. This bypasses slow on-board flash storage entirely.

```
┌───────────────────────────────┐
│  system_aicam_usb (V4L2 C++)  │
└───────────────┬───────────────┘
                │ Decodes Frame
                ▼
┌───────────────────────────────┐
│     openeye C++ Engine        │
└───────────────┬───────────────┘
                │ Converts to YUV420 & Writes to FIFO Pipe
                ▼
┌───────────────────────────────┐
│      /dev/shm/OpenEyeOut      │ <--- POSIX Shared Memory Pipe
└───────────────┬───────────────┘
                │ Low-latency stream extraction (Zero-Copy)
                ├───────────────────────────────┐
                ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│         lsl-pipe.py           │ │          recorder.py          │
│ (Sub-millisecond LSL stream)  │ │ (Accelerated FFmpeg Encoding) │
└───────────────────────────────┘ └───────────────────────────────┘
```

### Frame-Splitting Pipe Configuration

A standard 720p YUV420p raw frame requires:

$$\text{Frame Size} = 1280 \times 720 \times 1.5 = 1,382,400\text{ bytes}$$

If the software attempts to write all $1,382,400$ bytes to the pipe in a single system call, the operating system blocks the call because Linux named pipes are limited to $64\text{ KB}$ in memory. 

By splitting the frame into exactly 64 chunks of $21,600\text{ bytes}$ each, the C++ recorder feeds the pipe in small chunks, ensuring it stays well below the OS limit and prevents write operations from blocking:

```cpp
// From system_recorder.cpp
int BUF_SIZE = 21600; // 1382400 / 64 (Exactly 1/64th of a 720p YUV420p frame)
```

The consumer process (`recorder.py`) pulls these chunks from the pipe and forwards them directly to the hardware-accelerated video encoder (`h264_v4l2m2m` or `h264_omx`):

```bash
ffmpeg -y -f rawvideo -vcodec rawvideo -s 1280x720 -r 21 -pix_fmt yuv420p -i /dev/shm/OpenEyeOut -c:v h264_v4l2m2m -vb 5000k -qp 0 output.mp4
```

This pipeline architecture offloads the CPU-heavy video encoding tasks to the Raspberry Pi's GPU. This ensures that the core eye-tracking calculations can run at their target speeds without dropping frames.