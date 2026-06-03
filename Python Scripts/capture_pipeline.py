import time
import csv
import signal
import multiprocessing as mp
from pathlib import Path

# --- Import the updated linuxpy library ---
from linuxpy.video.device import Device, BufferType

# ==========================================
# Worker Function: Runs on its own CPU core
# ==========================================
def record_camera_worker(device_path, label, output_dir, width, height, fps, start_event, stop_event, session_stats_queue):
    
    # Ignore SIGINT in child processes — the main process handles Ctrl+C
    # and signals children via stop_event. This prevents ugly tracebacks.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    video_path = output_dir / f"{label}.mkv"
    csv_path = output_dir / f"{label}_timestamps.csv"
    
    first_timestamp_ns = None
    last_timestamp_ns = None
    frames_written = 0

    try:
        with Device(device_path) as cam:
            
            # Configure camera format and FPS via V4L2
            # linuxpy Device.set_format() expects: (buffer_type, width, height, pixel_format_str)
            # linuxpy Device.set_fps() expects: (buffer_type, fps)
            try:
                cam.set_format(BufferType.VIDEO_CAPTURE, width, height, "MJPG")
                cam.set_fps(BufferType.VIDEO_CAPTURE, fps)
                print(f"[{label.upper()}] Format set: {width}x{height} MJPG @ {fps} fps")
            except Exception as e:
                print(f"[{label.upper()}] Hardware config note: {e}")
                print(f"[{label.upper()}] Falling back to v4l2-ctl pre-set values.")
                
            # Open the file handles (Raw Binary for video, Text for CSV)
            with open(video_path, 'wb') as vid_out, open(csv_path, 'w', newline='') as csv_out:
                
                meta_writer = csv.writer(csv_out)
                meta_writer.writerow(["frame_index", "timestamp_ns"]) 
                
                print(f"[{label.upper()}] Ready. Waiting for sync signal...")
                start_event.wait() 
                print(f"[{label.upper()}] Recording Started.")

                fps_counter_start = time.monotonic()
                fps_frame_count = 0

                for frame in cam:
                    
                    if stop_event.is_set():
                        break

                    # --- Extract Sequence & Timestamp ---
                    # linuxpy Frame.frame_nb = buff.sequence (kernel sequence number)
                    # linuxpy Frame.timestamp = buff.timestamp.secs + buff.timestamp.usecs * 1e-6 (float seconds)
                    seq = frame.frame_nb
                    
                    # Convert the V4L2 kernel timestamp (float seconds) to nanoseconds
                    ts_ns = int(frame.timestamp * 1_000_000_000)
                    
                    if first_timestamp_ns is None:
                        first_timestamp_ns = ts_ns
                    last_timestamp_ns = ts_ns
                    
                    # Write raw MJPEG buffer to disk
                    vid_out.write(bytes(frame))
                    meta_writer.writerow([seq, ts_ns])
                    
                    frames_written += 1
                    fps_frame_count += 1
                    
                    # Print rolling FPS every 5 seconds for live monitoring
                    elapsed = time.monotonic() - fps_counter_start
                    if elapsed >= 5.0:
                        measured_fps = fps_frame_count / elapsed
                        print(f"[{label.upper()}] Live: {measured_fps:.1f} fps | Total frames: {frames_written}")
                        fps_counter_start = time.monotonic()
                        fps_frame_count = 0

    except Exception as e:
        print(f"[{label.upper()}] ERROR: {type(e).__name__} - {e}")
    finally:
        session_stats_queue.put({
            "camera": label,
            "start_time_ns": first_timestamp_ns,
            "end_time_ns": last_timestamp_ns,
            "frames_written": frames_written
        })
        print(f"[{label.upper()}] Saved {frames_written} frames to {output_dir}")

# ==========================================
# Main Control Process
# ==========================================
if __name__ == "__main__":
    
    session_name = input("\nEnter session name (e.g., Session_002_BenchTest): ").strip()
    
    if not session_name:
        session_name = f"Session_Auto_{int(time.time())}"
        print(f"[WARNING] No name provided. Defaulting to: {session_name}")

    # Set up Local Storage Path for now (Swap to SSD later)
    base_dir = Path("./Toyota-Kexxu_Data") 
    session_path = base_dir / session_name
    session_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[INFO] All data for this run will be saved to: {session_path}\n")
    
    # REQUIREMENT 1: Specific Resolutions and Formats
    eye_cfg = ("/dev/eye", "eye", session_path, 1280, 800, 60)
    front_cfg = ("/dev/front", "front", session_path, 1280, 720, 30)

    start_event = mp.Event()
    stop_event = mp.Event()
    stats_queue = mp.Queue()

    p_eye = mp.Process(target=record_camera_worker, args=(*eye_cfg, start_event, stop_event, stats_queue))
    p_front = mp.Process(target=record_camera_worker, args=(*front_cfg, start_event, stop_event, stats_queue))

    p_eye.start()
    p_front.start()

    time.sleep(2) 
    
    print("\n--- SYNCHRONIZING AND STARTING RECORDING ---")
    start_event.set() 
    
    try:
        print("Recording in progress... Press Ctrl+C to stop.\n")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n--- STOPPING RECORDING ---")
        stop_event.set() 

    p_eye.join(timeout=5)
    p_front.join(timeout=5)
    
    # Force terminate if processes didn't stop gracefully
    for p in [p_eye, p_front]:
        if p.is_alive():
            print(f"[WARNING] Force terminating {p.name}")
            p.terminate()
            p.join(timeout=2)

    # REQUIREMENT 2.3: Generate Generic session_meta.csv
    session_meta_path = session_path / "session_meta.csv"
    with open(session_meta_path, 'w', newline='') as meta_out:
        writer = csv.writer(meta_out)
        writer.writerow(["camera_label", "start_time_ns", "end_time_ns", "total_frames"])
        
        while not stats_queue.empty():
            stat = stats_queue.get()
            writer.writerow([stat["camera"], stat["start_time_ns"], stat["end_time_ns"], stat["frames_written"]])

    print(f"\n[SUCCESS] Session metadata saved to {session_meta_path}")
    print("--- PIPELINE SHUTDOWN COMPLETE ---")
