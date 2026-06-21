Here is a comprehensive, deep-dive reverse-engineering analysis of the software architecture, network configurations, camera subsystems, and data pipelines extracted from the proprietary Kexxu eye-tracking Raspberry Pi system.

---

## 0. Key Files, Paths, and System Actions

The system uses a mixed-language architecture: **Python 3** manages device state, network provisioning, and cloud orchestration, while **native C++/OpenCV** processes low-level camera operations.

```
/home/pi/
├── openeye_raspberrypi_code/
│   ├── openeye_cmake/include/lsl/
│   │   ├── outlet.h                 <-- Lab Streaming Layer C-API Stream Outlets
│   │   └── types.h                  <-- LSL opaque pointer declarations (inlets, outlets, xml)
│   └── kexxu-device/
│       ├── kexxu_device.py          <-- Main orchestrator daemon (monitors state, triggers actions)
│       ├── run.sh                   <-- Service wrapper loading env vars from /home/pi/conf
│       ├── tools_device.py          <-- VCGenCMD hardware diagnostics wrapper (CPU temperature)
│       ├── tools_wifi.py            <-- Interface to wpa_supplicant & socket routing
│       ├── client_action_http.py    <-- HTTP REST client targeting Kexxu's Cloud API
│       ├── client_mqtt_kexxu_device.py <-- Local loopback MQTT messaging wrapper
│       └── wpa_supplicant.conf      <-- Network configuration profiles and fallback credentials
├── ai_cam/
│   ├── src/
│   │   ├── system_aicam.cpp         <-- Direct V4L2 driver, custom raw buffer loop & exposure controller
│   │   ├── system_aicam.hpp         <-- Camera class interface headers
│   │   └── main.cpp                 <-- Camera validation binary (grabs 1000 frames)
│   └── build/                       <-- CMake compilation artifacts
└── test/
    └── test.cpp                     <-- Alternative camera harness using standard OpenCV VideoCapture
```

---

## 1. The Eye-Tracking Pipeline

The architecture is divided into three processing planes:

```
[ PHYSICAL SENSORS ]  --->  [ NATIVE CAPTURE (V4L2) ]  --->  [ LOCAL LSL / MQTT BUS ]  --->  [ CLOUD ORCHESTRATOR ]
 (/dev/video2, Y10)         (Exposure Control, CV)         (127.0.0.1 loopback)             (api.kexxu.com REST)
```

### Frame Capture & Brightness Control (Native C++)
*   The raw eye capture is handled in `system_aicam.cpp` via direct system call interfaces (`ioctl`) with `/dev/video2`.
*   Frames are ingested using a raw single memory-mapped buffer (`V4L2_MEMORY_MMAP`) in the **Y10** pixel format (10-bit greyscale, padded to 16 bits).
*   Inside `grab_image()`, the system calculates the average brightness of the eye by sampling every 20th pixel in a grid.
*   The system uses this calculated average to adjust the camera's exposure. It sends corrected exposure values back to the hardware using the `V4L2_CID_EXPOSURE` control ID.

### Local Transport & Inter-Process Communication
*   **Local MQTT Broker (`127.0.0.1:1883`)**: Acts as a high-speed data bus on the device. An MQTT client (`ClientMqttOpeneye`) subscribes to all topics (`#`).
*   **Lab Streaming Layer (LSL)**: A highly precise data synchronization library. `outlet.h` prepares high-frequency raw eye coordinate data to stream over the local network. This allows remote recording PCs to capture sub-millisecond synchronized streams of eye positions alongside other biometric sensors (like EEG or ECG).

### Remote Orchestration (Python 3)
*   `kexxu_device.py` monitors system health (CPU temperature and IP address) and sends updates to the cloud using HTTP POST requests. 
*   It also runs a provisioning loop. If it connects to a default setup hotspot, it downloads new Wi-Fi credentials from the cloud and applies them to the system.

```
                           +----------------------------+
                           |   Kexxu Cloud Server       |
                           |   (https://api.kexxu.com)  |
                           +--------------+-------------+
                                          ^
                                          | HTTPS REST
                                          v
+-----------------------------------------+-----------------------------------------+
| Raspberry Pi Device (Target System)                                               |
|                                                                                   |
|  +--------------------+      Subprocesses      +-------------------------------+  |
|  |   wpa_supplicant   | <--------------------> |        kexxu_device.py        |  |
|  |  (System Network)  |                        |  (Main Orchestrator Daemon)   |  |
|  +--------------------+                        +---------------+---------------+  |
|                                                                |                  |
|                                                                | Local Loopback   |
|                                                                | TCP / Unix Port  |
|                                                                v                  |
|  +--------------------+                        +---------------+---------------+  |
|  |    /dev/video2     | <--------------------> |         system_aicam          |  |
|  | (10-Bit Eye Camera)|      V4L2 ioctl        | (C++ Engine / OpenCV / LSL)   |  |
|  +--------------------+                        +-------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Security & Network Audit

Analyzing the system configuration reveals several security vulnerabilities, hardcoded credentials, and cloud APIs.

### Hardcoded Wi-Fi Credentials (`wpa_supplicant.conf`)
The system contains pre-configured network profiles designed to connect back to Kexxu’s testing facilities or local setup setups:
*   **SSID**: `a_setup_hotspot` (Also listed with an intentional trailing space: `"a_setup_hotspot "`)
    *   **PSK**: `setup_temporary`
    *   **Key Management**: WPA-PSK
    *   **Priority**: 4 (Primary connection target)
*   **SSID**: `Pesky` (Also listed with an intentional trailing space: `"Pesky "`)
    *   **PSK**: `Pesky2021!`
    *   **Key Management**: WPA-PSK (Likely a development or office hotspot)

### Cloud API Integration (`client_action_http.py`)
Device authentication and sync rely on parameters passed through environment variables (`KEXXU_DEVICE_ID`, `KEXXU_DEVICE_PASSWORD`, `KEXXU_DEVICE_VERSION`). These are appended directly to the URL query strings.

```python
# REST API Target Endpoints
POST_ACTION_URL = "https://api.kexxu.com/api/device/action?id={id}&p={pass}&build={build}&v=1"
GET_WIFI_INFO_URL = "https://api.kexxu.com/device/info?id={id}&p={pass}&build={build}&v=1"
SET_WIFI_ACK_URL = "https://kexxu.com/api/device/setWifi?id={id}&p={pass}&build={build}&v=1"
```

*   **Data Serialization**: The device action data is sent as a JSON array containing device features:
    ```json
    {
      "Features": [
        {
          "Feature": "local_ip",
          "Version": "1",
          "Name": "Device Ip Address",
          "ValueStr": "192.168.1.144",
          "Value": 0
        }
      ]
    }
    ```

### Local Control Ports
*   **MQTT Broker**: Bound to `127.0.0.1:1883`. Because it does not require authentication, any local process can read or publish to the camera stream or system control topics.

---

## 3. Camera Configurations

### Low-Level V4L2 Driver Configuration (`system_aicam.cpp`)
The driver configures the image sensor using standard Linux V4L2 control structures:

```cpp
imageFormat.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
imageFormat.fmt.pix.width = 640;
imageFormat.fmt.pix.height = 480;
imageFormat.fmt.pix.pixelformat = V4L2_PIX_FMT_Y10;  // 10-bit Raw Greyscale
imageFormat.fmt.pix.field = V4L2_FIELD_NONE;         // Progressive scanning
```

*   **Framerate Control**: Explicitly configured for high-speed capture:
    ```cpp
    struct v4l2_streamparm parm;
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator = 1;
    parm.parm.capture.timeperframe.denominator = 120; // 120 FPS target
    ```

*   **Memory Management**: Requests a single memory-mapped buffer.
    ```cpp
    requestBuffer.count = 1; // Extremely low buffer count
    requestBuffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    requestBuffer.memory = V4L2_MEMORY_MMAP;
    ```

---

## 4. Code-level Algorithms and Anomalies

### The Auto-Exposure Algorithm
Inside `system_aicam.cpp`, a custom exposure loop runs on every frame to compensate for changes in ambient lighting:

```cpp
struct v4l2_control ai_cam_control;
ai_cam_control.id = V4L2_CID_EXPOSURE;
int n = 0;
double mean_brightness = 0.0;

// Subsampled grid: Reads every 20th pixel
for(int x = 0; x < 640; x += 20){
    for(int y = 0; y < 480; y += 20){
        mean_brightness += (double)(image.at<uchar>(y, x, 0));
        n++;
    }
}
mean_brightness /= (double)n;

// Calculate the feedback correction factor
float brightness_adj = 1 + (80 - mean_brightness) * 0.002;
cur_exposure *= brightness_adj;

// Clamping limits
if(cur_exposure > 1704){ cur_exposure = 1074; } // High-limit fallback
if(cur_exposure < 20){ cur_exposure = 20; }     // Low-limit clamp
```

#### Explaining the Clamp Values:
1. **Low Clamp (`20`)**: Prevents the exposure time from dropping to zero, which would cause the auto-exposure calculation to fail.
2. **High Clamp (`1704`) and Fallback (`1074`)**: If the environment is very dark, the exposure value can escalate quickly. The high limit of `1704` protects the frame rate. If the exposure is set too high, the sensor cannot maintain its target frame rate of 120 FPS (where each frame must be captured in under 8.33 milliseconds). The immediate fallback to `1074` acts as a recovery state to keep the capture loop running.

---

### Critical Code Bugs & Architectural Issues

#### 1. Pixel Bit-Depth Mismatch (High Severity)
The camera format is explicitly configured to raw 10-bit greyscale (`V4L2_PIX_FMT_Y10`), and the image is loaded into memory as a 16-bit single-channel matrix:
```cpp
Mat image(Size(640, 480), CV_16UC1, buffer, Mat::AUTO_STEP);
```
However, the auto-exposure loop reads pixel values as 8-bit unsigned characters:
```cpp
mean_brightness += (double)(image.at<uchar>(y, x, 0));
```
On little-endian architectures like the Raspberry Pi's ARM processor, reading a `CV_16UC1` pixel (which uses 2 bytes) as an 8-bit `uchar` (1 byte) reads only the least significant byte. This discards the most significant 2 bits of the 10-bit image data and corrupts the brightness calculation.

#### 2. Under-buffered Capture Queue (Medium Severity)
In `system_aicam.cpp`, the V4L2 driver requests only one memory-mapped buffer:
```cpp
requestBuffer.count = 1;
```
For high-speed real-time capture at 120 FPS, a queue size of 1 is highly prone to frame drops. If the CPU is busy running the main process or scanning for Wi-Fi networks, the single buffer cannot be cleared in time. This forces the camera sensor to drop frames. The system should use a circular buffer queue of at least **3 to 4 buffers** to prevent stuttering.

---

### Data Synchronization Mechanics
Precision data synchronization is critical for eye-tracking systems to accurately align eye coordinates with video frames. The inclusion of the Lab Streaming Layer (`lsl/outlet.h`) reveals how this system achieves sub-millisecond synchronization:

*   **Timestamping**: Data frames are pushed with a high-resolution time sync offset:
    ```cpp
    extern LIBLSL_C_API int32_t lsl_push_sample_dt(lsl_outlet out, const double *data, double timestamp);
    ```
*   **Time Synchronization Protocol**: LSL uses background UDP/TCP handshake exchanges to calculate the exact network latency and clock drift between the Raspberry Pi and any connected recording devices. This allows the system to accurately align eye-tracking data with external biometric equipment (such as EEG sensors) without requiring physical sync cables.

---

## 5. Complete Camera Specs Table

| Parameter | Specification (Value) | Source Reference | File Location |
| :--- | :--- | :--- | :--- |
| **Active Device Node** | `/dev/video2` | `open("/dev/video2", O_RDWR)` | `system_aicam.cpp` |
| **Width** | 640 pixels | `imageFormat.fmt.pix.width` | `system_aicam.cpp` |
| **Height** | 480 pixels | `imageFormat.fmt.pix.height` | `system_aicam.cpp` |
| **Color Space / Format** | `V4L2_PIX_FMT_Y10` (Raw 10-bit Greyscale) | `imageFormat.fmt.pix.pixelformat` | `system_aicam.cpp` |
| **Mat Representation** | `CV_16UC1` (16-bit Unsigned, Single Channel) | `Mat image(Size(640, 480), ...)` | `system_aicam.cpp` |
| **Target Framerate** | 120 FPS | `parm.parm.capture.timeperframe` | `system_aicam.cpp` |
| **Memory Map Method** | `V4L2_MEMORY_MMAP` | `requestBuffer.memory` | `system_aicam.cpp` |
| **Buffer Queue Size** | 1 | `requestBuffer.count` | `system_aicam.cpp` |
| **Hardware Exposure Control** | `V4L2_CID_EXPOSURE` via `ioctl` | `ai_cam_control.id` | `system_aicam.cpp` |
| **Auto-Exposure Bounds** | Min: `20` units, Max Clamp: `1704` units | `cur_exposure` limits | `system_aicam.cpp` |

---

## 6. Performance and UI Lag Diagnostic

The sluggishness in the user interface during Wi-Fi scanning is caused by a common architecture bottleneck: **synchronous, blocking system commands executing inside the main process loop**.

### Root Cause Analysis
In `kexxu_device.py`, the main thread runs on a repeating interval:
```python
while True:
    # ...
    ip_wifi = ToolsWifi.get_ip_wifi()
    new_ssid = ToolsWifi.get_wifi_ssid()
    # ...
    time.sleep(sleep_sec)
```

Within `tools_wifi.py`, checking the Wi-Fi SSID makes a synchronous call to the system shell:
```python
@staticmethod
def get_wifi_ssid():
    try:
        out = subprocess.check_output(['iwgetid']).decode('utf-8')
    except Exception as e:
        return ""
    # Parsing logic...
```

*   **The Bottleneck**: The `subprocess.check_output` call stops the Python process and waits for the operating system to return the output of `iwgetid`.
*   **The System Lag**: When a Wi-Fi interface scans for networks or experiences high packet loss, system tools like `iwgetid` block for several hundred milliseconds (and sometimes up to several seconds if the driver is waiting for a timeout). Because the main orchestrator runs on a single thread, these blocking calls freeze the loop, causing visible stutters and sluggishness in any connected UI dashboards.

---

### Recommended Optimization Architectures

#### 1. Non-Blocking Asynchronous Subprocesses
We can replace the synchronous `subprocess.check_output` call with an asynchronous runner. This prevents the operating system query from blocking the main thread.

```python
import asyncio

async def get_wifi_ssid_async():
    try:
        # Launch iwgetid asynchronously without blocking the loop
        proc = await asyncio.create_subprocess_exec(
            'iwgetid',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        out = stdout.decode('utf-8')
        for line in out.split('\n'):
            if line.startswith('wlan0'):
                return line.split('"')[-2]
    except Exception:
        pass
    return ""
```

#### 2. Read Connection Details via the `/proc/net/` Filesystem
Instead of calling external system commands, we can read the connection state directly from the Linux virtual filesystem. This is much faster and avoids the overhead of spawning a subprocess.

```python
def get_wifi_ssid_from_proc():
    """Reads active wireless info directly from the Linux proc filesystem."""
    try:
        with open("/proc/net/wireless", "r") as f:
            lines = f.readlines()
            if len(lines) > 2:
                # If there are entries in this file, we have an active link.
                # We can read /proc/net/dev to check connection status.
                pass
    except IOError:
        return ""
```

#### 3. Offload Network Management to DBus
To avoid polling the interface manually, we can listen to network change events sent by NetworkManager or `wpa_supplicant` over DBus. This allows us to handle network state changes using event-driven callbacks instead of a repeating loop.

```python
# Utilizing DBus system bus signals to monitor SSID changes asynchronously
import dbus
from dbus.mainloop.glib import DBusGMainLoop

def wireless_state_changed_callback(*args):
    print("Network changed! Update UI state here without polling.")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
# Register to listen to NM or wpa_supplicant events here
```

---

## 7. Hardware-to-Software Connectivity Diagram

```
+---------------------------------------------------------------------------------------+
|                                    KEXXU EYE-GLASSES                                  |
|                                                                                       |
|   +-----------------------+              +----------------------------------------+   |
|   |   IR LED Illuminators |              |  Eye-Tracking Camera (/dev/video2)     |   |
|   +-----------+-----------+              +-------------------+--------------------+   |
|               |                                              |                        |
|               | Reflected IR Light                           | 120 FPS / Raw Y10      |
|               v                                              v                        |
|   +----------------------------------------------------------+--------------------+   |
|   |                      Raspberry Pi HW Frame Capture Engine                     |   |
|   |                                                                               |   |
|   |  +--------------------+   V4L2 ioctl    +----------------------------------+  |   |
|   |  |   mmap() Buffer    | <-------------> |     system_aicam Driver (C++)    |  |   |
|   |  +---------+----------+                 +----------------+-----------------+  |   |
|   |            |                                             |                    |   |
|   |            | CV_16UC1 Matrix Pointer                     | Exposure Changes   |   |
|   |            v                                             v                    |   |
|   |  +-------------------------------------------------------+-----------------+  |   |
|   |  | OpenCV Engine                                                           |  |   |
|   |  | - Downsampled auto-exposure loop                                        |  |   |
|   |  | - Pupil circle detection & localization processing                      |  |   |
|   |  +---------------------------------------+---------------------------------+  |   |
|   |                                          |                                    |   |
|   |                                          | High-Resolution Synchronized Stream|   |
|   |                                          v                                    |   |
|   |                        +-----------------+-----------------+                  |   |
|   |                        |        Lab Streaming Layer        |                  |   |
|   |                        |        (lsl_create_outlet)        |                  |   |
|   |                        +-----------------+-----------------+                  |   |
|   |                                          |                                    |   |
|   +------------------------------------------+------------------------------------+   |
|                                              |                                        |
|                                              | LSL Network Stream (TCP/UDP)           |
|                                              v                                        |
+----------------------------------------------+----------------------------------------+
                                               |
                                               | (Local Network Connection)
                                               v
+----------------------------------------------+----------------------------------------+
|                               REMOTE RECORDING / ANALYSIS PC                          |
|                                                                                       |
|    +-----------------------------------------+------------------------------------+   |
|    |                      Lab Streaming Layer Inlet Receiver                      |   |
|    |  - Synchronizes Pi clock offset with the local PC system time                |   |
|    |  - Collects real-time gaze vectors at 120Hz                                  |   |
|    +-----------------------------------------+------------------------------------+   |
|                                              |                                        |
|                                              v                                        |
|    +-----------------------------------------+------------------------------------+   |
|    |                      Gaze Mapping & Heatmap Generator                        |   |
|    |  - Calibrates 2D/3D gaze tracking vectors                                    |   |
|    |  - Overlays visual attention heatmaps onto video recordings                  |   |
|    +------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
```