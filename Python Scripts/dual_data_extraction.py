import v4l2py
import cv2
import time
import csv
import multiprocessing as mp
from pathlib import Path

def record_camera(device_path, label, output_dir, width, height, fps):
    # 1. Setup paths
    video_path = output_dir / f"{label}.mkv"
    csv_path = output_dir / f"{label}_metadata.csv"
    
    # 2. Initialize Video Writer (Direct MJPG Copy is faster, but for demo we use XVID/MP4)
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
    
    # 3. Open Device via v4l2py to access Buffer Metadata
    with v4l2py.Device(device_path) as cam:
        cam.video_capture.set_format(width, height, 'MJPG')
        cam.video_capture.set_fps(fps)
        
        with open(csv_path, 'w', newline='') as f:
            meta_writer = csv.writer(f)
            meta_writer.writerow(["sequence", "timestamp_ns", "frame_size"])
            
            print(f"[INFO] Started recording {label} on {device_path}")
            
            # Use the generator to get raw buffers
            for frame in cam.video_capture:
                # Extract Kernel Metadata (Row 3 & Row 4 compliance)
                seq = frame.sequence
                # Convert to nanoseconds for <1ms precision
                ts_ns = frame.timestamp.tv_sec * 1_000_000_000 + frame.timestamp.tv_usec * 1_000
                
                # Convert raw MJPG bytes to OpenCV image for the writer
                # NOTE: For maximum speed, save raw bytes directly to .mjpg file instead
                img = cv2.imdecode(frame.data, cv2.IMREAD_COLOR)
                writer.write(img)
                
                # Log to Sidecar CSV
                meta_writer.writerow([seq, ts_ns, len(frame.data)])
                
                # Break condition (External signal or frame limit)
                if seq > 1000: # Example limit
                    break

    writer.release()
    print(f"[SUCCESS] {label} saved to {video_path}")

if __name__ == "__main__":
    # SSD Path (Ensure this is mounted!)
    ssd_path = Path("/media/shaheer/ExternalSSD/ML_Data") 
    ssd_path.mkdir(parents=True, exist_ok=True)
    
    # Define Camera Configs based on your Specs [cite: 25, 1041]
    eye_cfg = ("/dev/eye", "eye_tracking", 1280, 800, 60)
    front_cfg = ("/dev/front", "world_view", 1920, 1080, 30)

    # Launch separate processes to avoid Python GIL bottleneck
    p1 = mp.Process(target=record_camera, args=(*eye_cfg, ssd_path))
    p2 = mp.Process(target=record_camera, args=(*front_cfg, ssd_path))

    p1.start()
    p2.start()
    
    p1.join()
    p2.join()