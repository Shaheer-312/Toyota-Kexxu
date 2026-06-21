#!/usr/bin/env python3
import os
import time
import logging
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# CONFIGURATION
# ==========================================
# IMPORTANT: Put your Gemini API key here
API_KEY = ""


TARGET_DIRS = [
    "/run/media/sherry/rootfs/home/pi/openeye_raspberrypi_code",
    "/run/media/sherry/rootfs/home/pi/ai_cam",
    "/run/media/sherry/rootfs/home/pi/test",
    "/run/media/sherry/rootfs/home/pi/installation",
    "/run/media/sherry/rootfs/etc/systemd/system/openeye.service",
    "/run/media/sherry/rootfs/etc/systemd/system/kexxu.service",
    "/run/media/sherry/rootfs/etc/systemd/system/goserver.service",
    "/run/media/sherry/rootfs/etc/systemd/system/recorder.service"
]
OUTPUT_DIR = "./ai_analysis_results"
LOG_FILE = "./ai_analyst.log"

# What to ignore
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".cache"}
IGNORE_EXTS = {".so", ".whl", ".bin"}

# System prompts tailored for Toyota-Eye-Wear / Kexxu reverse engineering
SYSTEM_INSTRUCTION = """
You are an expert embedded systems engineer and AI analyst. 
You are analyzing the internal filesystem of a proprietary 'Kexxu' eye-tracking Raspberry Pi. 
Your goal is to reverse-engineer its software architecture, camera pipelines (V4L2), 
data synchronization methods, and heatmap generation logic to help the user adapt 
it for their 'Toyota-Eye-Wear' project. Be precise, technical, and highlight any anomalies.
"""

# ==========================================
# SETUP
# ==========================================
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-3.5-flash", # Using Flash instead of Pro due to free-tier quota limits on Pro
    system_instruction=SYSTEM_INSTRUCTION
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def should_process(path: Path):
    if any(part in IGNORE_DIRS or part.startswith('.') for part in path.parts):
        return False
    if path.suffix.lower() in IGNORE_EXTS:
        return False
    return True

def analyze_code_batch(file_paths, batch_num):
    logging.info(f"Analyzing code batch {batch_num}...")
    combined_content = ""
    for p in file_paths:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                combined_content += f"\n\n--- FILE: {p} ---\n{f.read()}"
        except Exception as e:
            logging.error(f"Failed to read {p}: {e}")

    prompt = """
    Analyze the following batch of code and configuration files found on the Raspberry Pi. Analyze EVERYTHING DEEPLY, TAKE AS MUCH TIME AS YOU WANT AND GIVE ME DETAILED ANSWERS.
    0. I want you to tell me the IMPORTANT system/files/configs/scripts, where they are located and what they do, what they are for, what they are related to.  
    1. Identify what these specific files do within the broader eye-tracking pipeline.
    2. Look for hardcoded IP addresses, API keys, or cloud sync destinations.
    3. Look for camera configurations (resolution, framerate, V4L2 controls).
    4. Are there any pupil detection, UI dashboard, or data visualization algorithms here?
    5. I want details of the resolutions, fps, format for all the cameras, extract them.
    6. My project suffers from UI sluggishness caused by Wi-Fi scanning. Suggest optimization ideas.
    7. How is this embedded system connected to the software exactly
    
    Provide a detailed markdown summary.
    """
    
    try:
        response = model.generate_content([prompt, combined_content])
        with open(f"{OUTPUT_DIR}/analysis_batch_{batch_num}.md", "w") as f:
            f.write(response.text)
        logging.info(f"Batch {batch_num} analysis saved.")
    except Exception as e:
        logging.error(f"Gemini API error on batch {batch_num}: {e}")

def main():
    logging.info("Starting Autonomous Pi Analyst...")
    all_code_files = []
    
    # 1. Walk the directories
    for target in TARGET_DIRS:
        target_path = Path(target)
        if not target_path.exists():
            continue
            
        if target_path.is_file():
            if should_process(target_path):
                all_code_files.append(target_path)
            continue
            
        for root, dirs, files in os.walk(target):
            root_path = Path(root)
            if not should_process(root_path):
                continue
                
            for file in files:
                file_path = root_path / file
                if not should_process(file_path):
                    continue
                    
                if file_path.suffix.lower() in {".py", ".sh", ".service", ".env", ".json", ".conf", ".cpp", ".c", ".h"}:
                    all_code_files.append(file_path)

    # 2. Process Code in Batches (e.g., 20 files at a time)
    batch_size = 20
    for i in range(0, len(all_code_files), batch_size):
        batch = all_code_files[i:i + batch_size]
        analyze_code_batch(batch, i // batch_size + 1)
        time.sleep(15)  # Rate limiting for Free Tier (15 seconds between batches)
        
    # 3. Final Summary Generation
    logging.info("Generating final architectural summary...")
    # (You can expand this to read all the batch summaries and create one master report)
    
    logging.info("Analysis Complete. Agent going to sleep.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Process interrupted by user (CTRL+C). Exiting gracefully.")
        print("\nProcess interrupted by user. Exiting gracefully...")