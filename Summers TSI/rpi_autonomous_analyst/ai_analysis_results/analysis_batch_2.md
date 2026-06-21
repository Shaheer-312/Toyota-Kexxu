Here is a comprehensive reverse-engineering report of the Kexxu eye-tracking filesystem, analyzed to support your **Toyota-Eye-Wear** project.

---

# System Topology Map

The system uses a highly decentralized, multi-process architecture to decouple high-rate computer vision tasks from blocking network operations.

```
                  +--------------------------------------------------+
                  |                  KEXXU EYEWEAR                   |
                  +--------------------------------------------------+
                                           |
    +--------------------------------------+--------------------------------------+
    | (V4L2 Video Capture)                 | (Inter-Process Communication)        | (Network & Cloud Telemetry)
    v                                      v                                      v
+------------------------+          +------------------------+             +------------------------+
|   Scene Cam (/dev/video2)   |          | RAMDisk (/dev/shm)     |             | Mosquitto Local MQTT   |
|   1280x720 MJPEG @ 60Hz|          | serving raw JPEGs      |             | Broker (0.0.0.0:1883)  |
+------------------------+          +------------------------+             +------------------------+
    |                                      ^                                      ^
    | Decodes MJPEG                        | Writes images                        | Gaze Coordinates
    v                                      |                                      v
+------------------------+          +------------------------+             +------------------------+
|   Eye Cam (/dev/video0)   |--------->|     openeye Engine     |<----------->| Remote VerneMQ MQTT    |
|   1280x800 MJPEG @ 60Hz|          |   (TFLite Inference)   |             | (vmq.kexxu.com:80)     |
+------------------------+          +------------------------+             +------------------------+
    |                                      |                                      |
    | Decodes Greyscale                    | Writes YUV420 Frames                 | HTTP Uploads
    v                                      v                                      v
+------------------------+          +------------------------+             +------------------------+
|      OV9281 Sensor     |          | FFMPEG Recording Pipe  |             | Kexxu API Endpoint     |
|   Monochrome NIR IR    |          | (SystemRecorder)       |             | (api.kexxu.com)        |
+------------------------+          +------------------------+             +------------------------+
```

---

## 0. Key Files, Locations, and Roles

| File Path | Component | Target Device / Subsystem | Primary Role & Relationships |
| :--- | :--- | :--- | :--- |
| `/home/pi/.../src/openeye.cpp` | **Core Process** | System CPU, TFLite, Mosquitto | Coordinates the pipeline. Reads raw images from camera wrappers, runs TFLite inference, performs calibration mapping, handles MQTT messages, and coordinates recording. |
| `/home/pi/.../src/system_aicam_usb.cpp` | **USB Eye Camera Wrapper** | `/dev/video0` (OmniVision OV9281) | Directly configures and reads raw greyscale MJPEG frames from the eye camera. Integrates downsampling and automatic gain adjustments. |
| `/home/pi/.../src/system_scenecam.cpp` | **Scene Camera Wrapper** | `/dev/video2` (180° Point-of-View) | Controls POV camera capture. Configures MJPEG streaming formats, exposure parameters, and performs image rotation. |
| `/home/pi/.../src/system_aicam.cpp` | **Legacy CSI Camera Wrapper** | `/dev/video2` (MIPI CSI Interface) | Outdated module for a direct raw 10-bit MIPI sensor (`V4L2_PIX_FMT_Y10`). Serves as a reference for direct hardware registers. |
| `/home/pi/.../src/kexxu_api.cpp` | **API Client Interface** | `api.kexxu.com`, AWS Cloud | Manages cloud data asset transfers. Implements chunked HTTP POST/Multipart uploads for video and session telemetry over `curlpp`. |
| `/home/pi/.../bin/conf.json` | **Runtime Configuration** | File System / Memory | Contains runtime calibration coefficients, crop windows, feature states, and network addresses. |
| `/home/pi/.../bin/wifi-cli.py` | **Network Provisioning** | `wpa_supplicant` | Parses custom Wi-Fi setup string structures from QR codes and rewrites `/etc/wpa_supplicant/wpa_supplicant.conf`. |

---

## 1. Eye-Tracking Pipeline Breakdown

```
 [Eye-Camera Capture] ---> [ROI Cropper] ---> [Model 1 (Coarse Center)] ---> [Model 2 (Sub-pixel Center)] ---> [Geometric Gaze Mapping] ---> [MQTT/LSL Output]
```

### Step 1: Image Acquisition and Downsampling (`system_aicam_usb.cpp`)
The system captures frame buffers using Memory Mapped I/O (`V4L2_MEMORY_MMAP`). Instead of decoding the full 1280x800 MJPEG frame using resource-intensive decompression libraries, the system optimizes image ingestion:
* Grabs raw compressed JPEG buffers from `/dev/video0`.
* Decodes the buffer using OpenCV `imdecode(rawData, IMREAD_COLOR)`.
* Skips color space conversions and downsamples in a single loop step:
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
  This custom conversion loop downsamples the image to a flipped 640x400 monochrome representation inside `image_grab` without allocating intermediary matrices.

### Step 2: Region of Interest (ROI) Cropping (`openeye.cpp`)
To minimize processing overhead, a localized region of interest is cropped out of `image_grab` based on the config parameters `win_x`, `win_y`, and a bounding box size of 360x360 pixels:
```cpp
Mat crop = ai_cam_image( Range(conf.win_x, conf.win_x2), Range(conf.win_y, conf.win_y2) );
```

### Step 3: Coarse Pupil Center Detection (`openeye.cpp`)
The 360x360 raw crop is resized to 90x90 pixels and its pixel values are normalized to $[-0.5, 0.5]$ range:
```cpp
data[i] = static_cast<float>(crop.at<uchar>(y,x))/256. - 0.5;
```
This normalized vector is evaluated by **Model 1** (`pupil-4x-90.tflite`). The model outputs a probability distribution across 90 bins representing the $X$ and $Y$ axes. The system calculates the peak index to establish the coarse coordinates:
```cpp
out_x += conf.win_y; // Offset back to camera frame coordinates
out_y += conf.win_x;
```

### Step 4: Sub-Pixel Target Optimization (`openeye.cpp`)
Once the coarse pupil coordinates are located, the engine crops a high-precision 120x120 window around this center and feeds it to **Model 2** (`pupil-1x-120-v2.tflite`). The output of Model 2 is evaluated to compute the sub-pixel center offset:
```cpp
out_x = crop_x + offsets2_x;
out_y = crop_y + offsets2_y;
```

### Step 5: Geometric Gaze Mapping (`openeye.cpp`)
The calculated pupil center coordinates are offset using the system calibration values:
```cpp
float eye_c_x = conf.calibration_center_x + float(out_y + conf.win_x);
float eye_c_y = conf.calibration_center_y + float(out_x - conf.win_y);
```
Next, a multivariate regression polynomial maps these pupil coordinates ($x, y$) into coordinate vectors ($G_x, G_y$) relative to the perspective camera frame. This step corrects optical distortions and perspective skew:

$$G_x = c_{x\_x}x + c_{x\_y}y + c_{x\_xx}x^2 + c_{x\_xxx}x^3 + c_{x\_xxy}x^2y + c_{x\_xxyy}x^2y^2 + c_{x\_yy}y^2 + c_{x\_xyy}xy^2 + c_{x\_xy}xy$$

$$G_y = c_{y\_x}x + c_{y\_y}y + c_{y\_xx}x^2 + c_{y\_xxy}x^2y + c_{y\_xxyy}x^2y^2 + c_{y\_yy}y^2 + c_{y\_yyy}y^3 + c_{y\_xyy}xy^2 + c_{y\_xy}xy$$

### Step 6: Telemetry Broadcast (`openeye.cpp`)
The normalized coordinates ($G_x, G_y$) are wrapped inside a JSON string containing exact microsecond epoch timestamps and pushed out via the local Mosquitto MQTT broker on loopback interfaces.

---

## 2. Hardcoded Credentials and Cloud Destinations

### Local Telemetry Broker (On-Device Host)
* **Local MQTT IP**: `tcp://0.0.0.0:1883`
* **Local Topics**:
  * `devices/{device_id}/feature` (Diagnostics)
  * `devices/{device_id}/eyetracking` (Raw Pupil Telemetry JSON)
  * `devices/{device_id}/markers` (Calibration Points Data)
  * `devices/{device_id}/recording` (Start/Stop Video Processing Commands)

### Remote Telemetry Broker (VerneMQ Cloud Instance)
* **Remote Broker URL**: `tcp://vmq.kexxu.com:80` (Falls back to legacy target: `tcp://mqtt-1.kexxu.com:80`)
* **Topic Structure**: `eventstream/{device_id}/lastEvent`

### Web Services & Backend Interfaces
* **Device Provisioning API**: `https://api.kexxu.com/api/device/action?id=`
* **Data Upload Destination**: `http://18.192.205.32:3000/api/{type}/upload?id=`
  * *Note: IP `18.192.205.32` points to an EC2 instance hosted in the AWS Frankfurt region (`eu-central-1`). This server acts as the primary telemetry collection endpoint.*

---

## 3. Camera Configurations and V4L2 Parameters

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

### Eye Camera Control Pipeline (`system_aicam_usb.cpp`)
* **Target Node**: `/dev/video0`
* **Resolution**: 1280x800
* **Format**: `V4L2_PIX_FMT_Y10` requested, falls back to raw MJPEG decoding.
* **Stream Timing**: Pushed to 60 FPS using `V4L2_BUF_TYPE_VIDEO_CAPTURE` structures:
  ```cpp
  parm.parm.capture.timeperframe.numerator = 1;
  parm.parm.capture.timeperframe.denominator = 60;
  ```
* **V4L2 Control Registries**:
  * **Analog Gain**: Managed dynamically via `V4L2_CID_GAIN` within a bounded scale ($[0, 100]$):
    ```cpp
    ai_cam_control.id = V4L2_CID_GAIN;
    ai_cam_control.value = int(cur_gain);
    ```

### POV Scene Camera Control Pipeline (`system_scenecam.cpp`)
* **Target Node**: `/dev/video2`
* **Resolution**: 1280x720
* **Format**: `V4L2_PIX_FMT_MJPEG`
* **V4L2 Control Registries**:
  * **Auto Exposure**: Supports manual exposure lock for IR-illuminated environments.
    ```cpp
    control.id = V4L2_CID_EXPOSURE_AUTO;
    control.value = V4L2_EXPOSURE_MANUAL; // Locked during active IR tracking
    // For visible light, uses: V4L2_EXPOSURE_APERTURE_PRIORITY
    ```
  * **Absolute Exposure Value**: Fixed to a brief interval (value `10` register units) to prevent high-speed motion blur.

---

## 4. On-Device Algorithms

### Sub-Pixel Peak Estimation Algorithm
Instead of using basic thresholding methods that are prone to noise, the peak of the pupil probability density is calculated along the $X$ and $Y$ axis output matrices of the neural network:
```cpp
float max = 0;
float max_i = 0;
for(int i = 0; i < 90; i++){
    v = offsets_raw[i]; 
    if(v > max){
        max = v;
        max_i = float(i);
    }
}
out_x = max_i; // Estimated coarse coordinate peak
```

### Real-Time Landmark Visualization
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
if(uint8_t(p[x])>201 && uint8_t(p[x+1])>201 && uint8_t(p[x+2])>201) { // GBR
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

## 5. Multi-Camera Pipeline Configurations

| Camera Target | Node Route | Frame Capture Resolution | Framerate | Pixel Format | Primary Pipeline Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Monochrome IR Eye Camera** | `/dev/video0` | $1280 \times 800$ | $60\text{ Hz}$ | `MJPEG` / `Y10` (monochrome raw) | Captures close-up frames of the eye under IR illumination for real-time tracking. |
| **Wide-Angle POV Scene Camera** | `/dev/video2` | $1280 \times 720$ | $60\text{ Hz}$ | `MJPEG` | Captures perspective environmental video and matches gaze vector telemetry. |

---

## 6. Root-Cause Analysis: Wi-Fi Induced Sluggishness

The sluggish performance of your UI is caused by a threading bottleneck inside the pipeline's loop structure:

```
[Main Thread] ---> [V4L2 Grab Frame] ---> [TFLite Inference] ---> [Blocking API / System Call] ---> [Mosquitto Network Flush] ---> [Loop Blocked]
                                                                          |
                                                      The loop stalls here while wpa_cli runs
```

### The Bottleneck Mechanism
In `openeye.cpp`, the active processing loop relies on synchronous blocking calls to the network stack:
```cpp
while(!has_ip_wlan0() && conf.qrcodescan_enabled){
    if(scan_wifi_qr(scene_cam)){
       // ...
       system("./wifi-cli.py add-qr ..."); // High-overhead fork/exec block
    }
}
```
Whenever `wifi-cli.py` triggers `wpa_cli -i wlan0 reconfigure`, the Linux kernel suspends the executing thread while negotiating connection endpoints.

Furthermore, active background Wi-Fi scanning (`iwlist scan` or `wpa_supplicant` background probing) forces the Wi-Fi card to switch channels to listen for beacon frames. This halts network traffic on your current channel, stalling the TCP sockets used by your MQTT connections.

Because the main loop features synchronous network blocks (`tok_local->wait()`), any network delay directly drops the camera capture frame rates.

### Optimization Blueprints for your Toyota-Eye-Wear Project

To fix the sluggishness, decouple the network stack and configuration processing from the high-rate video processing loop:

#### Optimization Blueprint A: Decouple Thread Executions (C++ Core)
Move the network configuration, telemetry reporting, and file upload pipelines to dedicated worker threads. The primary capture loop must never wait on network responses.

```cpp
// Create an asynchronous background thread for network tasks
std::thread wifi_worker_thread = std::thread([this]() {
    while(running) {
        if (pending_wifi_update) {
            // Run system configuration calls on a separate thread
            system("wpa_cli -i wlan0 reconfigure");
            pending_wifi_update = false;
        }
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }
});
wifi_worker_thread.detach();
```

#### Optimization Blueprint B: Asynchronous Telemetry Submissions
Replace blocking MQTT publishing calls with non-blocking, asynchronous telemetry dispatches. Do not call `.wait()` on the returned token in your main thread loop:

```cpp
// Change this blocking pattern:
// tok_local = top_local_eyetracking.publish(j.dump());
// tok_local->wait();

// To this non-blocking asynchronous pattern:
top_local_eyetracking.publish(j.dump()); // Fire and forget. Let the driver handle the buffer queue.
```

#### Optimization Blueprint C: Disable Background Scan Probing
Modify the host wireless configuration profiles in `/etc/wpa_supplicant/wpa_supplicant.conf` to stop background scanning when connected to a network:

```wpa_supplicant
# Append to the top of your wpa_supplicant config
ap_scan=1
# Stop scanning background frequencies while connected
bgscan="simple:20:-75:300"
```

---

## 7. Hardware-Software Integration Map

```
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                                                                         LINUX OS KERNEL CORE                                                                      |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------+
                                                                                   |
                      +------------------------------------------------------------+------------------------------------------------------------+
                      | V4L2 Driver Interfaces                                     | memory mapped I/O (MMAP)                                   | Telemetry Pipeline
                      v                                                            v                                                            v
+---------------------------------------------+              +---------------------------------------------+              +---------------------------------------------+
|          Hardware Camera Sensors            |              |          RAMDisk System Buffer              |              |                Local Inter-Process          |
|      /dev/video0  &  /dev/video2            |              |              /dev/shm                       |              |                 Communication (IPC)         |
+---------------------------------------------+              +---------------------------------------------+              +---------------------------------------------+
                      |                                                            |                                                            |
                      | Captures MJPEG Streams                                     | Serves Eye/Scene JPEGs                                     | Pushes Gaze Coordinates
                      v                                                            v                                                            v
+---------------------------------------------+              +---------------------------------------------+              +---------------------------------------------+
|           V4L2 Capture Wrappers             |------------->|            Shared Memory Mount              |<------------>|                MQTT Broker                  |
|    (system_aicam_usb / system_scenecam)     |              |           (Eye & Scene Buffers)             |              |            (Mosquitto Local Daemon)         |
+---------------------------------------------+              +---------------------------------------------+              +---------------------------------------------+
```

### The Interface Map

#### V4L2 Camera Ingestion Layer
* Custom drivers map `/dev/video0` (gaze camera) and `/dev/video2` (POV scene camera) to circular memory structures mapped using `mmap()`.
* Synchronization and non-blocking reads are handled via standard POSIX file descriptors multiplexed using `select()` system calls.

#### Low-Latency IPC Layer
Instead of using slow disk writes or Unix domain sockets, the system uses the virtual RAM filesystem `/dev/shm/` to share image frames:
* **The Frame Buffer**: Saves processed frames to `/dev/shm/mem_serve/eye_tmp.jpg` and uses atomic renames (`rename()`) to update the active frame `/dev/shm/mem_serve/eye.jpg`. This prevents race conditions and read/write collisions when other processes load the images.

#### High-Throughput Recording Pipeline
The system avoids complex, resource-heavy encoding processes in the main thread by utilizing Unix pipes to stream raw video frames directly to background processes:
```cpp
// Pushes raw YUV-I420 frames directly into a background FFMPEG pipe
Mat pipe_img;
cv::cvtColor(overlay_img, pipe_img, COLOR_BGR2YUV_I420);
const char* temp = reinterpret_cast<char const*>(pipe_img.data);
recorder->write_to_pipe(temp);
```
By converting frames to YUV420 in memory and writing raw bytes directly to a pipe, the system offloads CPU-heavy H.264/MP4 encoding tasks to a dedicated system-level FFMPEG subprocess.

#### Hardware Level Output Control
An integrated `wiringPi` wrapper maps system status changes to external physical indicators (e.g., active tracking, network connection loss, or calibration success) using physical GPIO pins:
```cpp
// Triggers an external buzzer using active-high GPIO pin state changes
wiringPiSetup();
pinMode(27, OUTPUT);
digitalWrite(27, 1); // Generates audible alert pulses
```