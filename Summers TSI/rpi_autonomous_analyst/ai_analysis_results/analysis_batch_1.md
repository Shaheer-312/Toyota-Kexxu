### 0. Critical System Inventory, Mapping, and Topography

This proprietary Kexxu hardware system operates on a dual-pathway architecture: a high-performance **C++ engine** handles real-time computer vision and hardware-accelerated video recording, while a **Python/Go orchestration layer** manages cloud synchronization, telemetry, local networking, and peripheral integration.

#### File Inventory and System Map

```
/home/pi/
├── conf                              <-- Master system environment variables (IPs, credentials, serial configs)
└── openeye_raspberrypi_code/
    ├── enable_i2c_vc.sh              <-- Low-level script enabling the VideoCore (GPU) I2C interface
    ├── script_install.py             <-- Installer dependency runner (empty stub in this batch)
    ├── go-server/
    │   ├── run.sh                    <-- Spawns the Go API web server
    │   └── go-server-raspberry       <-- Compiled Go binary (serves on-device UI and local dashboard)
    ├── lsl-pipe/
    │   ├── lsl-pipe.py               <-- Lab Streaming Layer (LSL) bridge; reads from Shared Memory IPC
    │   └── openeye_out               <-- Symlink or point to /dev/shm/openeye_out FIFO
    ├── start/
    │   ├── start-kexxu-device.sh     <-- Systemd daemon launcher for Python cloud/hardware state-machine
    │   ├── start-tf-eyetrack.sh      <-- Systemd daemon launcher for Tensorflow-based eye tracker (C++ binary)
    │   └── start-scene-cam.sh        <-- Systemd daemon launcher for local MJPEG scene camera server
    ├── recorder/
    │   ├── run.sh                    <-- Script spawning recorder.py
    │   ├── recorder.py               <-- Telemetry manager, GPS reader, audio capturing & video-rec backend
    │   └── ffmpeg                    <-- Optimized statically linked FFmpeg binary supporting RPi hardware encoders
    ├── utils/
    │   ├── mat2tensor.h              <-- C++ OpenCV-to-TensorFlow memory mapping header
    │   ├── mipi_raw10_to_jpg.py      <-- Demuxer/unpacker for 10-bit raw MIPI CSI-2 camera data
    │   └── mono_to_jpg.py            <-- Grayscale frame extractor for raw 8-bit IR eye-tracking cameras
    ├── systemd/
    │   ├── tf-eyetrack.service       <-- Systemd unit for real-time neural gaze estimation
    │   ├── recorder.service          <-- Systemd unit for synchronized audio/video/data logging
    │   └── kexxu.service             <-- Systemd unit for core device manager and cloud sync daemon
    ├── wifi-cli/
    │   ├── install.sh                <-- Deploys CLI scripts to target binary directory
    │   ├── wifi-cli.py               <-- Direct interface to wpa_supplicant.conf and networking stack
    │   └── saved.json                <-- JSON configuration of known WiFi SSID profiles
    ├── scene-cam/
    │   └── scene-cam.py              <-- MJPEG-over-HTTP web server streaming video from V4L2 index 0
    └── openeye_cmake/
        └── src/
            ├── system_recorder.cpp   <-- Low-level C++ high-performance FIFO video streaming pipe writer
            └── system_recorder.hpp   <-- C++ recording class interfaces
```

#### Systemd Service Architecture

The system's core execution model is fully managed via systemd. It decouples high-priority, real-time image processing from secondary telemetry logging.

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

---

### 1. Architectural Blueprint of the Eye-Tracking Pipeline

The Kexxu system runs a highly decoupled, multi-process streaming pipeline. Rather than processing frames within a single, heavy monolithic process, it splits operations into dedicated execution stages. This keeps the C++ eye tracker fast while avoiding frame drops when writing high-bitrate video or processing GPS data.

```
                                      +-------------------------+
                                      |   Scene / Eye Camera    |
                                      |     (V4L2 Device)       |
                                      +------------+------------+
                                                   |
                                                   | Raw Video Frames
                                                   v
                                      +-------------------------+
                                      |      tf-eyetrack        |
                                      |  (Tensorflow/C++ Core)  |
                                      +------------+------------+
                                                   |
                                                   | YUV420p Raw Stream
                                                   v
                                      +-------------------------+
                                      |   /dev/shm/OpenEyeOut   |
                                      |  (POSIX Shared Memory)  |
                                      +------------+------------+
                                                   |
                             +---------------------+---------------------+
                             |                                           |
                             | Read Raw Bytes                            | Read Raw Bytes
                             v                                           v
                +-------------------------+                 +-------------------------+
                |    lsl-pipe.py          |                 |     recorder.py         |
                |  (Real-Time Analytics)  |                 | (FFmpeg Hardware Enc)   |
                +-------------------------+                 +------------+------------+
                                                                         |
                                                                         | h264_v4l2m2m / H.264 MP4
                                                                         v
                                                            +-------------------------+
                                                            |  Local Storage / Media  |
                                                            +-------------------------+
```

#### Detailed Pipe Flow

1. **Ingestion Stage**: The eye-tracking binary (`tf-eyetrack`) opens the camera feeds. It uses local camera inputs, processes them via its inner CNN model, and outputs a synchronized video stream overlayed with coordinates.
2. **IPC Shared Memory Bridge**: The C++ application opens a POSIX Named Pipe (FIFO) at `/dev/shm/OpenEyeOut` (or `/dev/shm/openeye_out` for LSL). Because `/dev/shm` is mapped directly to RAM (tmpfs), this write operation bypasses slow flash storage (SD Card/eMMC) entirely.
3. **Double-Consumer Decoupling**:
   - **Performance Validation Stream (`lsl-pipe.py`)**: Reads raw frames from the pipe, calculates frame delivery rates dynamically, and forwards high-speed gaze coordinates.
   - **Encoding/Archival Stream (`recorder.py`)**: Spawns an underlying, optimized hardware-accelerated instance of FFmpeg, consuming the raw `/dev/shm/OpenEyeOut` stream.
4. **Hardware Transcoding Engine**: FFmpeg compresses this raw video in real-time. It uses the Raspberry Pi Broadcom VideoCore GPU (`h264_v4l2m2m` or the legacy Broadcom OpenMAX IL `h264_omx` encoder) to compress YUV420p data directly into `.mp4` files at high bitrates without stressing the CPU.

---

### 2. Security & Network Audits (Hardcoded Assets & Cloud Sync)

This system is configured to work with the Kexxu cloud backend while managing local configuration fallbacks. Below are the hardcoded variables, URLs, and static keys found in the source files.

#### Extracted Hostnames and Endpoints

- **Cloud API URL**: `https://api.kexxu.com/api/device/action`
  - Used for sending runtime telemetry packets via HTTP POST. It appends the device ID and authentication keys as query parameters.
- **Cloud MQTT Broker**: `vmq.kexxu.com`
  - This is a Vernemq MQTT broker operating on Port `80` (likely bypassed via WebSockets or reverse proxy to avoid corporate firewalls).
- **Local Loopback Broker**: `0.0.0.0` on Port `1883`
  - Used by the local Python orchestrator to communicate with local services (such as the C++ binary).

#### Hardcoded Credentials & Authentication Tokens

* **Local MQTT Configuration**:
  * **Client ID**: `"rec-" + KEXXU_DEVICE_ID`
  * **Static Username**: `"kexxu"`
  * **Static Password**: `"vySgEjzJ524Er6PUaK6zKAKUe5MfAP"`
* **Local Provisioning WiFi Network Credentials**:
  Stored in `/home/pi/openeye_raspberrypi_code/wifi-cli/saved.json`, these credentials provide default access profiles:

```json
{
  "saved": [
    { "ssid": "a_setup_hotspot", "passw": "setup_temporary" },
    { "ssid": "Pesky",           "passw": "Pesky2021!" },
    { "ssid": "test",            "passw": "12345678" }
  ]
}
```

#### Telemetry Serialization Protocol

The system constructs and transmits structured telemetry packets to the Kexxu cloud API:

```json
{
  "Features": [
    {
      "Feature": "status",
      "Version": "1",
      "Name": "Device Status",
      "ValueStr": "starting sensor recorder process",
      "Value": 0
    }
  ]
}
```

---

### 3. Deep Camera Configuration & V4L2 Diagnostics

The camera pipeline is configured for dual-camera inputs: an outward-facing **Scene Camera** and high-speed **Eye/Pupil Cameras** using IR illumination.

#### The Scene Camera Pipeline

The script `scene-cam.py` initializes the scene camera using V4L2:

```python
capture = cv2.VideoCapture(0)
```

By default, OpenCV requests the camera’s fallback resolution (typically $640 \times 480$ YUYV or MJPEG at 30 FPS). The commented-out code reveals the intended production settings:

```python
# capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 640);
# capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 480);
```

#### Transcoding Configuration Matrix

When a recording starts, the telemetry processor spawns a subprocess running FFmpeg. It is configured with the following command-line flags:

```bash
ffmpeg -y -f rawvideo -vcodec rawvideo -s 1280x720 -r 21 -pix_fmt yuv420p -i /dev/shm/OpenEyeOut -progress - -nostats -c:v h264_v4l2m2m -vb 5000k -qp 0 output_recording.mp4
```

These parameters define the recording configuration:

- **Source Pixel Format (`-pix_fmt`)**: `yuv420p`
- **Output Bitrate (`-vb`)**: `5000k` (5 Mbps constant target bitrate)
- **Quantization Parameter (`-qp`)**: `0` (lossless mode)
- **Target Video Resolution**: $1280 \times 720$ (HD 720p)
- **Target Frame Rate**: `21 FPS` (Python implementation) / `18 FPS` (C++ implementation)

#### System Bottlenecks & Critical Performance Anomalies

##### Critical Thread Blocking in `scene-cam.py`
The MJPEG server reads camera frames inside an HTTP request handler (`CamHandler` class):

```python
rc, img = capture.read()
imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
jpg = Image.fromarray(imgRGB)
tmpFile = BytesIO()
jpg.save(tmpFile, 'JPEG')
```

Because this is a synchronous, blocking call inside the HTTP request loop, **each incoming client request halts the camera reader**. If a client experiences network latency, the main camera stream stalls, which drops the frame rate of the eye-tracking system.

##### Frame Rate Mismatch (C++ vs. Python)
- In `system_recorder.cpp`, FFmpeg is configured for **18 FPS**:
  ```cpp
  strcpy(newargv[8], "-r");
  strcpy(newargv[9], "18");
  ```
- In `recorder.py`, the dynamic queue launches FFmpeg configured for **21 FPS**:
  ```python
  "-r", "21"
  ```

This difference of 3 FPS between the C++ data writer and the Python/FFmpeg reader will cause **frame interpolation errors, audio-to-video sync drift, and constant underflow warnings** on the FIFO pipe during long recording sessions.

##### POSIX Pipe Write Splitting Buffer Constraints
In `system_recorder.cpp`, writes to the named pipe are split into custom chunks using a specific buffer size:

```cpp
int BUF_SIZE = 21600; // 1382400/64 (Exactly 1/64th of a 1280x720 YUV420p frame)
```

A standard 720p YUV420p raw frame requires:

$$\text{Frame Size} = 1280 \times 720 \times 1.5 = 1,382,400\text{ bytes}$$

If the software attempts to write all $1,382,400$ bytes to the pipe in a single system call, the operating system blocks the call because Linux named pipes are limited to $64\text{ KB}$ in memory. 

By splitting the frame into exactly 64 chunks of $21,600\text{ bytes}$ each, the C++ recorder feeds the pipe in small chunks, ensuring it stays well below the OS limit and prevents write operations from blocking.

---

### 4. Computer Vision & ML Core Analysis

The underlying C++ binary (`tf-eyetrack`) loads a pre-trained neural network (likely a custom MobileNet-backbone model or a specialized DeepGaze variant) via TensorFlow's C++ interface to handle real-time pupil detection and gaze vector estimation.

```
+------------------------------------------------------------+
|                       mat2tensor.h                         |
|                                                            |
|  [cv::Mat Input Frame] -> [Convert to CV_32FC3]            |
|                               |                            |
|                               v                            |
|  [Normalize Pixels by 1/255.0]                             |
|                               |                            |
|                               v                            |
|  [Tensor Allocation: Shape {1, Height, Width, Channels}]   |
|                               |                            |
|                               v                            |
|  [Raw Data Pointer Cast] -> [In-Memory TensorFlow Tensor]  |
+------------------------------------------------------------+
```

#### Image-to-Tensor Conversion Analysis

In `mat2tensor.h`, raw camera frames from OpenCV (`cv::Mat`) are converted directly into TensorFlow input tensors.

The primary function copies and scales pixel data in a single step:

```cpp
tensorflow::Tensor Mat2Tensor(cv::Mat &img, float normal = 1/255.0) {
    tensorflow::Tensor image_input = tensorflow::Tensor(
        tensorflow::DT_FLOAT, 
        tensorflow::TensorShape({1, img.size().height, img.size().width, img.channels()})
    );

    float *tensor_data_ptr = image_input.flat<float>().data();
    cv::Mat fake_mat(img.rows, img.cols, CV_32FC(img.channels()), tensor_data_ptr);
    img.convertTo(fake_mat, CV_32FC(img.channels()));

    fake_mat *= normal; // Normalize to [0.0, 1.0]

    return image_input;
}
```

This method is highly optimized:
- It allocates a TensorFlow `Tensor` with a batch size of `1`.
- It maps a custom OpenCV `cv::Mat` (`fake_mat`) **directly onto the underlying raw pointer of the TensorFlow tensor memory block**.
- Running `img.convertTo` writes the processed frame directly into TensorFlow's allocated memory, eliminating the need for an intermediate copy operation.

#### 10-Bit Raw MIPI Unpacking

The system supports specialized high-speed cameras using the script `mipi_raw10_to_jpg.py`. Low-cost IR cameras often output CSI-2 data in raw 10-bit MIPI packets. 

To save bandwidth, this format packs four 10-bit pixels into a 5-byte block. The unpacking math is implemented as follows:

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

### 5. Consolidated Camera Specifications Matrix

The dynamic analysis of all configurations and processing scripts reveals three distinct camera profiles:

| Camera Function | Sensor Interface Type | Pixel Format (Raw) | Target Processing Format | Target Resolution | Processing Frame Rate | Hardware Encoding Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Scene Camera** | USB / V4L2 Interface (`/dev/video0`) | YUYV / MJPEG | RGB24 / JPEG | $1280 \times 720$ (HD) | **21 FPS** (Recording) <br> **18 FPS** (C++ Pipe Engine) | High-speed `h264_v4l2m2m` |
| **Eye Camera (10-Bit)** | MIPI CSI-2 | RAW10 Bayer Pattern | Grayscale / BGR | Variable (Sensor native) | Variable (Real-time tracking) | Software Extraction via Python |
| **Eye Camera (8-Bit)** | CSI-2 / USB | Grayscale (8-bit) | Grayscale (mono) | Variable (32-byte alignment) | Variable | Software raw parsing |

---

### 6. Mitigating UI Sluggishness Caused by Wi-Fi Scanning

#### The Root Cause

Your UI sluggishness is caused by **thread blocking during network operations**. In `wifi-cli.py`, new wireless profile additions are handled synchronously:

```python
cmd_str = 'wpa_cli -i wlan0 reconfigure'
cmd = shlex.split(cmd_str)
out = subprocess.run(cmd, capture_output=True) # <-- BLOCKS EXECUTION
```

Running `wpa_cli reconfigure` blocks the thread while the system reloads the configuration and restarts the DHCP handshake. This delay propagates through the network stack and causes several issues:

1. **Kernel Driver Holds (WLAN Driver Lock)**: The wireless card driver (`brcmfmac` on the RPi) blocks access to the network interface when updating configurations. This stalls any active local socket operations.
2. **D-Bus & Local Socket Blocks**: Because `recorder.py` and the MQTT client communicate over local TCP ports (`127.0.0.1`), network state updates block the local loopback interface, which delays telemetry transfers and drops video frames.

#### Structural Optimization Ideas for your "Toyota-Eye-Wear" Project

To prevent network operations from blocking your user interface, implement these architectural fixes:

##### Migrate to Asynchronous Non-Blocking Subprocesses
Instead of blocking your Python scripts with `subprocess.run`, run your system calls asynchronously using `asyncio`:

```python
import asyncio

async def add_wifi_async(ssid, passw):
    # Perform writing asynchronously
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, write_wpa_supplicant_conf, ssid, passw)
    
    # Run wpa_cli non-blocking
    process = await asyncio.create_subprocess_exec(
        'wpa_cli', '-i', 'wlan0', 'reconfigure',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    # Let the UI loop run while waiting for the network interface to reconfigure
    stdout, stderr = await process.communicate()
```

##### Decouple Local IPC Telemetry
Configure your local services to bypass the network stack entirely for local communication. Instead of using standard TCP/IP loopbacks (`0.0.0.0:1883`) for your MQTT messages, configure Mosquitto to use **UNIX Domain Sockets** (`/var/run/mosquitto.sock`). 

Because UNIX domain sockets run entirely within the virtual filesystem, local communications remain fast and uninterrupted even when the wireless interface is disabled, scanning, or changing states.

##### Offload WiFi Management to a Separate Process Group
Assign the high-priority real-time processes (such as `tf-eyetrack`) to dedicated CPU cores, and move the networking tasks to a different core using CPU affinity. You can configure this in your systemd service file:

```ini
# tf-eyetrack.service
CPUAffinity=0-2  # Bind the eye-tracker to Cores 0, 1, and 2

# wifi-cli / NetworkManager processes
CPUAffinity=3    # Force all networking tasks to Core 3
```

##### Replace Dynamic Scanning with Background Probing
Avoid triggering on-demand network scans while recording is active. Instead, use a background service to search for known networks, and suspend scanning entirely when the user initiates a recording session.

---

### 7. Hardware-to-Software Connectivity Integration Map

This system relies on precise mappings between software modules and physical hardware pins to handle synchronization and raw data ingestion.

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

* **Camera Control Channel (I2C VC)**:
  - **Hardware Interface**: Physical pins 27 and 28 (configured as the VideoCore I2C channel).
  - **Driver Mapping**: Enabled via `enable_i2c_vc.sh` (`dtparam=i2c_vc=on`). This allows the system to configure the camera module's internal registers directly (such as adjusting exposure, gain, and horizontal/vertical blanking).
* **High-Speed Gaze Input (CSI-2 Bus)**:
  - **Hardware Interface**: 15-pin/22-pin FPC Flex Cable connector feeding raw frame data directly to the Broadcom ISP.
  - **Software Demuxing**: Managed by `mipi_raw10_to_jpg.py` to unpack raw MIPI patterns without dropping frames.
* **Telemetry and Localization Channel (UART)**:
  - **Hardware Interface**: Raspberry Pi physical pins 8 and 10 (`TXD0` / `RXD0` mapped to serial interface `/dev/ttyAMA0`).
  - **Telemetry Parsing**: The core `recorder.py` service opens a serial connection at `9600 Baud` to read incoming NMEA GPS frames. It parses `$GNGGA` sentences on the fly and converts them into JSON objects to publish location updates.
* **Audio Capture (ALSA Hardware Bus)**:
  - **Hardware Interface**: USB Microphone or external audio codec mapped to ALSA index card 2 (`hw:2,0`).
  - **Software Capture**: Spawns an independent FFmpeg recording instance to capture mono, 1-channel audio at $44.1\text{ kHz}$ to save synchronized sound files alongside the video data:
    ```bash
    ffmpeg -ar 44100 -ac 1 -f alsa -i hw:2,0 -fflags flush_packets output.mp3
    ```

---

### 8. Crucial Bug Fixes for Toyota-Eye-Wear

If you are porting this code base directly to your **Toyota-Eye-Wear** project, resolve this high-priority bug immediately:

#### The Systemd Configuration Path Mismatch (System-Breaking Bug)

In the provided files, the physical directories are named:
`/home/pi/openeye_raspberrypi_code/` (spelled **raspberry** with a `p`).

However, the systemd unit files use a misspelled directory path:
`/home/pi/openeye_rasberrypi_code/` (spelled **rasberry** without a `p`).

##### Impact
All systemd services (`tf-eyetrack.service`, `recorder.service`, and `kexxu.service`) will fail to launch on boot with a `File Not Found` error. 

##### Fix
Correct the paths in your systemd service files to match your physical directory structure, or create a symlink on your target system to resolve the mismatch:

```bash
ln -s /home/pi/openeye_raspberrypi_code /home/pi/openeye_rasberrypi_code
```