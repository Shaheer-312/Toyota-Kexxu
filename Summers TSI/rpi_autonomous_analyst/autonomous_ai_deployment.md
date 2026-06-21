# Laptop-Based AI Analyst Guide (Mounted SD Card)

This guide provides instructions to run the AI agent locally from your Ubuntu laptop, analyzing the files on the Kexxu Raspberry Pi SD card that you've inserted and mounted.

## 1. The Python AI Agent (`pi_autonomous_analyst.py`)

This script walks through the mounted SD card filesystem, analyzes code, and processes the files using the Gemini API. All outputs are saved locally on your laptop.

```python
#!/usr/bin/env python3
import os
import time
import logging
from pathlib import Path
from google import genai
from google.genai import types

# ==========================================
# CONFIGURATION
# ==========================================
# IMPORTANT: Put your Gemini API key here
API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# Scan the mounted SD card
TARGET_DIRS = ["/run/media/sherry/rootfs/home", "/run/media/sherry/rootfs/etc/systemd/system"]  
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
client = genai.Client(api_key=API_KEY)

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
    Analyze the following batch of code and configuration files found on the Raspberry Pi. Analyze EVERYTHING DEEPLY, TAKE AS MUCH TIME AS YOU WANT.
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
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=[prompt, combined_content],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION
            )
        )
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
        if not os.path.exists(target):
            logging.warning(f"Target directory not found: {target}")
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
        time.sleep(5)  # Rate limiting
        
    # 3. Final Summary Generation
    logging.info("Generating final architectural summary...")
    
    logging.info("Analysis Complete. Results are saved in the local directory.")

if __name__ == "__main__":
    main()
```

## 2. Running the Analyst

Since you've plugged the SD card into your laptop, the procedure is very simple:

1. **Verify Mount:** Ensure the SD card is mounted at `/run/media/sherry/rootfs/`
2. **Activate your Environment:** Ensure you are using your `.venv` environment where `google-genai` is installed.
3. **Execute:** Run the script from the directory you want the outputs saved in:
   ```bash
   python3 pi_autonomous_analyst.py
   ```
   You will find the reports under `./ai_analysis_results` in the same directory.

## 3. Tailored Prompts for the AI

If you want to modify the script to ask specific questions based on your `Toyota-Eye-Wear` goals, inject these prompts into the `analyze_code_batch` function:

* **Prompt for Hardware Synchronization:** "I am trying to resolve an eye-camera frame-rate synchronization issue in my project. Look closely at this code batch. Do you see any V4L2 multiprocessing logic, frame buffering, or hardware syncing mechanisms (like GPIO triggers) between multiple camera streams?"
* **Prompt for UI/Dashboard Analysis:** "My project suffers from UI sluggishness caused by Wi-Fi scanning. Does this Kexxu code contain a web dashboard? If so, how does it handle real-time status updates (like upload progress or network state) without blocking the main camera thread?"
* **Prompt for Video Storage/Sync:** "I need an autonomous data offloading pipeline. Does this code integrate with `rclone` or Google Drive? How does it trigger the sync (e.g., on boot, scheduled, or via an API endpoint)?"
