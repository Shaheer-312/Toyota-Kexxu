import v4l2py
import time
import csv
import multiprocessing as mp
from pathlib import Path

# ==========================================
# Worker Function: Runs on its own CPU core
# ==========================================
def record_camera_worker(device_path, label, output_dir, width, height, fps, start_event, stop_event, session_stats_queue):
    """
    Direct-to-disk worker for a single camera.
    Bypasses OpenCV completely to write raw MJPEG bytes to disk.
    Extracts kernel-level v4l2_buffer metadata.
    """
    
    # 1. Setup Output Paths (Direct to SSD)
    video_path = output_dir / f"{label}.mkv"
    csv_path = output_dir / f"{label}_timestamps.csv"
    
    # 2. Trackers for the session_meta.csv
    first_timestamp_ns = None
    last_timestamp_ns = None
    frames_written = 0

    try:
        # 3. Open Device via v4l2py
        with v4l2py.Device(device_path) as cam:
            
            # Apply your specific format requirements
            cam.video_capture.set_format(width, height, 'MJPG')
            cam.video_capture.set_fps(fps)
            
            # Open the file handles (Raw Binary for video, Text for CSV)
            # Using raw bytes (.mkv extension, but technically an MJPEG bitstream)
            # This is the fastest possible way to write the data, zero CPU overhead.
            with open(video_path, 'wb') as vid_out, open(csv_path, 'w', newline='') as csv_out:
                
                meta_writer = csv.writer(csv_out)
                meta_writer.writerow(["frame_index", "timestamp_ns"]) # Header
                
                print(f"[{label.upper()}] Ready. Waiting for sync signal...")
                start_event.wait() # Hold here until the main process says "GO"
                print(f"[{label.upper()}] Recording Started.")

                # Iterate through the V4L2 generator
                for frame in cam.video_capture:
                    
                    # Check if the main process told us to stop
                    if stop_event.is_set():
                        break

                    # --- Extract Kernel Metadata ---
                    seq = frame.sequence
                    ts_ns = frame.timestamp.tv_sec * 1_000_000_000 + frame.timestamp.tv_usec * 1_000
                    
                    # Record start/end bounds for session meta
                    if first_timestamp_ns is None:
                        first_timestamp_ns = ts_ns
                    last_timestamp_ns = ts_ns
                    
                    # --- Direct-to-Disk Writes ---
                    # Write the raw MJPEG payload directly to the file
                    vid_out.write(frame.data)
                    # Write the sidecar metadata
                    meta_writer.writerow([seq, ts_ns])
                    
                    frames_written += 1

    except Exception as e:
        print(f"[{label.upper()}] ERROR: {e}")
    finally:
        # Push our session stats back to the main process
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
    
    print("\n==========================================")
    print("   COMPONENT 2: DATA CAPTURE PIPELINE")
    print("==========================================")
    
    # --- REQUIREMENT: Dynamic Session Naming ---
    session_name = input("\nEnter session name (e.g., Session_002_BenchTest): ").strip()
    
    # SAFETY FALLBACK: If user just presses Enter, generate a unique timestamp
    if not session_name:
        session_name = f"Session_Auto_{int(time.time())}"
        print(f"[WARNING] No name provided. Defaulting to: {session_name}")

    # --- Configuration ---
    # Define the Base Directory (Change this to your SSD path when ready)
    base_dir = Path("./Toyota-Kexxu_Data") 
    
    # Create the specific session folder
    session_path = base_dir / session_name
    session_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[INFO] All data for this run will be saved to: {session_path}\n")
    
    # REQUIREMENT 1: Specific Resolutions and Formats
    eye_cfg = ("/dev/eye", "eye", session_path, 1280, 800, 60)
    front_cfg = ("/dev/front", "front", session_path, 1280, 720, 30)

    # --- Synchronization Tools ---
    start_event = mp.Event()
    stop_event = mp.Event()
    stats_queue = mp.Queue()

    # --- Initialize Workers ---
    p_eye = mp.Process(target=record_camera_worker, args=(*eye_cfg, start_event, stop_event, stats_queue))
    p_front = mp.Process(target=record_camera_worker, args=(*front_cfg, start_event, stop_event, stats_queue))

    p_eye.start()
    p_front.start()

    # Give cameras 2 seconds to initialize their internal buffers
    time.sleep(2) 
    
    # REQUIREMENT 1 (Synchronous Recording): Trigger both workers simultaneously
    print("\n--- SYNCHRONIZING AND STARTING RECORDING ---")
    start_event.set() 
    
    try:
        # Keep recording until you press Ctrl+C in the terminal
        print("Recording in progress... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n--- STOPPING RECORDING ---")
        stop_event.set() # Tell workers to break their loops gracefully

    # Wait for both workers to finish writing to disk
    p_eye.join()
    p_front.join()

    # --- REQUIREMENT 2.3: Generate Generic session_meta.csv ---
    session_meta_path = session_path / "session_meta.csv"
    with open(session_meta_path, 'w', newline='') as meta_out:
        writer = csv.writer(meta_out)
        writer.writerow(["camera_label", "start_time_ns", "end_time_ns", "total_frames"])
        
        # Pull the stats generated by each worker thread
        while not stats_queue.empty():
            stat = stats_queue.get()
            writer.writerow([stat["camera"], stat["start_time_ns"], stat["end_time_ns"], stat["frames_written"]])

    print(f"\n[SUCCESS] Session metadata saved to {session_meta_path}")
    print("--- PIPELINE SHUTDOWN COMPLETE ---")