# Embedded System Selection — Component 2: Waist-Case Processor

## Your Exact Requirements (Derived from Project Docs)

Before comparing boards, here's what your system **actually needs** based on your architecture (C1 pipeline, decoupled design, 5-6 hour battery):

| Requirement | Why | Priority |
|---|---|---|
| **USB 3.0 host** (≥2 ports) | Simultaneous dual USB cameras + external SSD | 🔴 Critical |
| **Linux (Ubuntu/Debian)** with V4L2 | Your entire pipeline is V4L2 + linuxpy | 🔴 Critical |
| **6-core+ ARM CPU** | Multiprocessing pipeline — 1 core/camera + OS + headroom | 🔴 Critical |
| **≥ 8GB RAM** | Dual video stream buffers + OS | 🟡 Important |
| **Low power (≤7W typical)** | 5-6 hour battery life on ~37Wh pack | 🟡 Important |
| **Compact size** | Fits in waist/pocket case | 🟡 Important |
| **Hardware H.264 encoder** | Future C2 architecture — storage efficiency | 🟢 Future |
| **GPIO** | IR LED control | 🟢 Future |
| **WiFi/BLE** | Data transfer, gaze streaming | 🟢 Future |
| **GPU / NPU** | Future on-device pupil detection | 🟢 Future |

---

## The Candidates

### 1. 🟢 Orange Pi 5 (RK3588S) — RECOMMENDED START

| Spec | Detail |
|---|---|
| **SoC** | Rockchip RK3588S (4× Cortex-A76 @ 2.4GHz + 4× Cortex-A55 @ 1.8GHz) |
| **RAM** | 4/8/16GB LPDDR4X |
| **USB** | 1× USB 3.0, 2× USB 2.0, 1× USB-C (OTG) |
| **HW Video Encoder** | ✅ Yes — RK3588 VPU (H.264/H.265/VP9 encode) via Rockchip MPP |
| **HW Video Decoder** | ✅ Yes — up to 8K60 decode |
| **GPU** | Mali-G610 MP4 |
| **NPU** | 6 TOPS (for future on-device AI) |
| **GPIO** | 26-pin header (I2C, SPI, UART, GPIO) |
| **WiFi/BLE** | Optional M.2 module |
| **Size** | **62mm × 100mm** (credit-card sized) |
| **Weight** | ~46g |
| **Power** | 3-5W idle, 6-10W load |
| **OS** | Ubuntu 22.04/24.04, Armbian, Debian |
| **Price** | **~$70-100** (8GB) |

#### Why It's the Best Starting Point

1. **Hardware video encoder included** — The RK3588S has a dedicated VPU that encodes H.264/H.265. This directly enables your **Architecture C2** (GStreamer H.264 pipeline) without CPU overhead. Neither the Jetson Orin Nano nor the Raspberry Pi 5 have this.

2. **Smallest form factor** — At 62×100mm and 46g, it's the most compact option. This matters for your waist-mounted case design.

3. **Best price-to-capability ratio** — $70-100 gets you 8-core CPU, hardware encoder, 6 TOPS NPU, and GPU. The Jetson Orin Nano costs $249 for similar CPU power but *no* hardware encoder.

4. **Sufficient USB** — 1× USB 3.0 + 2× USB 2.0. Your cameras are MJPEG (compressed), so bandwidth requirements are moderate (~5-8 MB/s total). You can run cameras on USB 3.0 via a hub and SSD via USB 2.0, or vice versa.

5. **6 TOPS NPU** — Future-proofs for on-device pupil detection (your downstream components).

6. **Power efficient** — 3-5W idle, peaks at ~8W under dual-stream capture. With a 37Wh battery pack (10,000mAh @ 3.7V), you get **~5-6 hours** at typical workload.

#### Limitations to Know

- **USB 3.0 is only 1 port** — you'll need a powered USB 3.0 hub to split between cameras + SSD, or use the USB 2.0 ports for cameras (MJPEG bandwidth is low enough).
- **HW encoder access** uses Rockchip's proprietary MPP library, not standard V4L2 encoding. You'll need `rkmpp`-enabled FFmpeg or GStreamer — this requires some setup but is well-documented.
- **Community is smaller than Raspberry Pi** — but Armbian support is excellent.

---

### 2. 🟡 NVIDIA Jetson Orin Nano Super — BEST AI PLATFORM (but overkill)

| Spec | Detail |
|---|---|
| **SoC** | NVIDIA Orin (6× Cortex-A78AE @ 1.5GHz) |
| **RAM** | 8GB LPDDR5 |
| **USB** | **4× USB 3.2 Gen2** (10Gbps each!) + 1× USB-C |
| **HW Video Encoder** | ❌ **No NVENC** — software encoding only |
| **HW Video Decoder** | ✅ Yes — NVDEC (up to 4K60 H.265) |
| **GPU** | 1024 CUDA cores + 32 Tensor cores (Ampere) |
| **NPU** | 67 TOPS |
| **GPIO** | 40-pin header |
| **WiFi/BLE** | M.2 slot (module sold separately) |
| **Size** | ~100mm × 79mm (dev kit is larger) |
| **Power** | 7W / 15W configurable modes; idle ~4.7W |
| **OS** | JetPack (Ubuntu 22.04 based) |
| **Price** | **~$249** (dev kit) |

#### Strengths

1. **Best USB connectivity** — 4× USB 3.2 Gen2 ports. Plug in both cameras AND the SSD without any hub. Each gets its own dedicated bandwidth. This **completely eliminates your Unknown U1** (USB bandwidth contention).

2. **67 TOPS AI performance** — Massively overkill for capture, but if your project ever needs real-time pupil detection or gaze inference on-device, nothing else comes close.

3. **Best Linux/NVIDIA ecosystem** — JetPack is rock-solid, CUDA is well-documented, massive community.

4. **Power modes** — `nvpmodel` lets you switch between 7W (battery) and 15W (performance) modes.

#### Why It's NOT #1

> [!CAUTION]
> **The Jetson Orin Nano has NO hardware video encoder (NVENC).** This was a critical finding from my research. Your System Concept Document assumes NVENC availability (Assumption A7) — this assumption is **invalid** for the Orin Nano. Only the Orin NX ($399-699) has NVENC. This means your Architecture C2 (H.264 hardware encoding) cannot be implemented on the Orin Nano without CPU-based software encoding, which will consume significant CPU resources at 60fps.

- **Most expensive** at $249 — 2.5-3× the cost of the Orange Pi 5.
- **Higher power draw** — 4.7W idle, 7-15W under load. You'll need a larger battery for 5-6 hours.
- **Larger and heavier** than the Orange Pi 5.
- **Overkill** — 67 TOPS and 1024 CUDA cores are wasted on a capture-only pipeline.

---

### 3. 🟡 Raspberry Pi 5 — EASIEST TO START (but limited)

| Spec | Detail |
|---|---|
| **SoC** | Broadcom BCM2712 (4× Cortex-A76 @ 2.4GHz) |
| **RAM** | 4/8GB LPDDR4X |
| **USB** | 2× USB 3.0, 2× USB 2.0 |
| **HW Video Encoder** | ❌ **No** — removed from Pi 4 → Pi 5 |
| **HW Video Decoder** | ✅ Yes (H.265 4Kp60) |
| **GPU** | VideoCore VII |
| **NPU** | ❌ None |
| **GPIO** | 40-pin header |
| **WiFi/BLE** | ✅ Built-in WiFi 5 + BLE 5.0 |
| **Size** | 85mm × 56mm |
| **Weight** | ~47g |
| **Power** | 2.5-3W idle, 10-12W peak |
| **OS** | Raspberry Pi OS, Ubuntu 24.04 |
| **Price** | **~$60-80** (8GB) |

#### Strengths

1. **Largest community** — Any problem you encounter, someone has solved it. Fastest debugging.
2. **Built-in WiFi + BLE** — No extra modules needed for your F6 data export mechanisms.
3. **Cheapest** — $60-80 for the 8GB model.
4. **Two USB 3.0 ports on separate controllers** — You can put one camera on each controller to avoid bandwidth contention.
5. **2× MIPI CSI connectors** — If you ever upgrade from USB cameras to CSI cameras, the Pi 5 has dedicated camera ports.
6. **Referenced in your research papers** — Raj et al. (2023) demonstrated real-time pupil detection on a Pi 4. Your evaluator will recognize this.

#### Why It's NOT #1

- **No hardware video encoder** — Same problem as Jetson Orin Nano. H.264 encoding is CPU-only.
- **No NPU** — No path to on-device AI inference.
- **Only 4 cores** — Your pipeline uses multiprocessing (1 core per camera). With only 4 cores, you have just 2 cores left for OS + any future processing.
- **Higher peak power** — Can spike to 10-12W under load, reducing battery life.
- **Only 4-core** vs 8-core on Orange Pi 5 and 6-core on Jetson.

---

### 4. 🔵 Orange Pi 5 Plus (RK3588) — THE POWERHOUSE

Same SoC family as Orange Pi 5 but with the full RK3588 (not RK3588S):

| Spec | Detail |
|---|---|
| **USB** | **2× USB 3.0** + USB-C |
| **HW Video Encoder** | ✅ Yes — same RK3588 VPU |
| **Networking** | 2× 2.5Gb Ethernet |
| **PCIe** | PCIe 3.0 (fast NVMe) |
| **Size** | 100mm × 75mm (larger) |
| **Price** | **~$120-160** (8GB) |

Better than Orange Pi 5 for USB (2× USB 3.0), but larger, heavier, and more expensive. Consider this if you find the single USB 3.0 port on the standard Orange Pi 5 too limiting.

---

### 5. 🔵 NVIDIA Jetson Orin NX — THE IDEAL (if budget allows)

| Spec | Detail |
|---|---|
| **HW Video Encoder** | ✅ **Yes — NVENC** (H.264/H.265/AV1) |
| **USB** | 4× USB 3.2 Gen2 |
| **GPU** | CUDA cores (Ampere) |
| **NPU** | Up to 100 TOPS |
| **Price** | **~$399-699** |

This is the board your documents *assumed* you'd use. It has NVENC, making your Architecture C2 fully viable. But at $399-699, it's likely outside FYP budget.

---

## Head-to-Head Comparison

| Criteria (from your Trade Study) | Orange Pi 5 | Jetson Orin Nano | Raspberry Pi 5 | Orin NX |
|---|:---:|:---:|:---:|:---:|
| **HW Video Encoder** | ✅ RK VPU | ❌ None | ❌ None | ✅ NVENC |
| **USB 3.0 Ports** | 1 | 4 | 2 | 4 |
| **CPU Cores** | 8 (4×A76+4×A55) | 6 (A78AE) | 4 (A76) | 6-8 (A78AE) |
| **NPU** | 6 TOPS | 67 TOPS | ❌ | 70-100 TOPS |
| **Idle Power** | ~3-5W | ~4.7W | ~2.5-3W | ~5-7W |
| **Load Power** | ~6-10W | ~7-15W | ~10-12W | ~10-25W |
| **Size (mm)** | 62×100 | ~100×79 | 85×56 | ~100×79 |
| **Weight** | 46g | ~80g+ | 47g | ~80g+ |
| **Price** | **$70-100** | $249 | $60-80 | $399-699 |
| **5-6hr Battery (37Wh)** | ✅ ~5-6hr | ⚠️ ~4-5hr | ⚠️ ~3-5hr | ❌ ~2-3hr |
| **V4L2 Camera Support** | ✅ | ✅ | ✅ | ✅ |
| **Community Size** | Medium | Large | Largest | Large |
| **WiFi/BLE Built-in** | ❌ (module) | ❌ (module) | ✅ | ❌ (module) |

---

## Recommendation

### Start With: **Orange Pi 5 (8GB) — ~$80**

```
Your Pipeline (today):
  USB Cameras → V4L2/linuxpy → MJPEG → SSD (C1 architecture)
  
Orange Pi 5 handles this with:
  ✅ 8-core CPU for multiprocessing
  ✅ USB 3.0 for cameras + SSD
  ✅ Ubuntu/V4L2 support
  ✅ 3-5W idle = 5-6hr battery life
  ✅ Hardware H.264 encoder ready for C2 evolution
  ✅ 6 TOPS NPU for future on-device AI
  ✅ Smallest form factor (62×100mm, 46g)
  ✅ Cheapest capable option ($70-100)
```

### Best Possible: **Jetson Orin NX — ~$500**

If budget allows (or Toyota sponsors hardware), the Orin NX gives you everything — NVENC, 4× USB 3.2, massive AI capability. But it's 5-7× the cost and harder to power on battery.

### What to Avoid: **Jetson Orin Nano for this project**

At $249 with no hardware encoder, it's the worst value proposition. You pay NVIDIA premium pricing but don't get the one feature (NVENC) that justifies it. The Orange Pi 5 gives you a hardware encoder for 1/3 the price.

> [!IMPORTANT]
> **Critical update for your documents:** Your System Concept Stage Document (Assumption A7) assumes the Jetson Orin Nano has hardware H.264 encoding. **It does not.** Only the Orin NX and above have NVENC. This invalidates Architecture C2 on the Orin Nano and actually strengthens the case for the Orange Pi 5 (RK3588S), which *does* have hardware encoding via Rockchip VPU.

---

## Migration Path

Your `capture_pipeline.py` uses `linuxpy` + V4L2, which is Linux-standard. **Zero code changes** are needed to migrate from your Dell laptop to any of these boards — just:

1. Install Ubuntu on the board
2. Set up `python3 -m venv .venv` + `pip install linuxpy`  
3. Create the same udev rules (`/dev/eye`, `/dev/front`)
4. Run `capture_pipeline.py`

The entire pipeline is hardware-agnostic by design — that's the advantage of building on V4L2.
