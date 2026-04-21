# 🚀 Team Onboarding & Project Log
*Welcome to VisionMetrics! This document is meant for all team members to understand exactly what we are doing step-by-step. If you clone this repository, strictly follow these instructions to get the AI working on your computer.*

## Phase 1: Environment Setup (What we did so far)
Before the AI can run, it needs its own "virtual computer" inside your computer so its libraries don't mess with yours. We set this up using a Virtual Environment (`venv`).

### HOW TO REPLICATE THIS (For Teammates):
1. **Download the Code:** Download this whole folder from GitHub to your computer.
2. **Open your Terminal** (or Command Prompt).
3. **Navigate to the folder (CRITICAL):** You MUST tell the terminal exactly where the project is. If you are not in the right folder, the commands below will fail with an error. 
   - Type `cd` followed by a space, then drag the project folder from your "File Explorer" into the terminal (it will automatically paste the path).
   - Alternatively, type the path manually (use the path where you saved the project):
   ```bash
   cd "C:\Users\YourName\Desktop\AI_AD_PROJECT"
   ```
   *Tip: In VS Code, go to **File > Open Folder...** and select this folder. The terminal will then open in the correct spot automatically.*

4. **Create the Virtual Environment:**
   ```bash
   python -m venv venv
   ```
5. **Activate the Environment:**
   - **On Windows:** `.\venv\Scripts\activate`
   - **On Mac/Linux:** `source venv/bin/activate`
   *If successful, you will see `(venv)` appear at the beginning of your terminal line.*

6. **Install the AI Brains (PyTorch, YOLO, etc.):**
   ```bash
   pip install -r requirements.txt
   ```
*(Note: Downloading PyTorch is huge, so this might take 3-5 minutes depending on your Wi-Fi!)*

---

## Phase 2: Connecting the "Eye" (Camera Testing)
*Status: [COMPLETED]*

**What we built:**
We wrote a small Python script (`src/inference/detect.py`) that uses **OpenCV** to turn on your webcam and **YOLOv8** to draw boxes around any humans it sees.

### HOW TO RUN THE AI (Step-by-Step):
Once you have done Phase 1 (setting up the virtual environment), you can test the AI yourself.
1. **Ensure your Virtual Environment is active** (Type `.\venv\Scripts\activate` and look for the `(venv)` label).
2. **Run the script:**
   ```bash
   python src/inference/detect.py
   ```
3. A popup window should appear showing your webcam feed with a box around you! 
4. **Important:** Click on the popup video window and press the **`q`** key on your keyboard to close it safely. (Do NOT just close the window with the 'X' button).

---

## Phase 3: Data Collection & Gaze Tracking
*Status: [IN PROGRESS]*

**Phase 3: Data Collection & Gaze Tracking**
*Status: [COMPLETED]*

**What we built:**
We upgraded `src/training/data_collector.py` into a scientific recording tool. It calculates:
- **Yaw:** Head turn (Left/Right).
- **Pitch:** Head tilt (Up/Down).
- **Distance:** How far the user is from the camera.

### HOW TO RECORD DATA FOR THE AI (VITRINA PROTOCOL):
*CRITICAL:* Before recording, you must read `docs/HARDWARE_PROTOCOL_VITRINA.md` to understand how to simulate a wide jewelry stand.
1. Mount your phone on a tripod exactly where it will be during the live presentation. Connect it using Iriun Webcam or Camo.
2. (Optional) If using your phone, change `cv2.VideoCapture(0)` to `1` or `2` in `data_collector.py`.
3. Ensure your Virtual Environment is active.
4. Run the script: `python src/training/data_collector.py`
5. **Recording 'L' (Engagement):** Follow the Vitrina sweep protocol. Stand at 0.5m, 1m, and 2m away. Look at the left, center, and right edges of the imaginary "vitrina". Tap `L` repeatedly.
6. **Recording 'A' (Distraction):** Look at your phone, look at the ceiling, gaze away. Tap `A` repeatedly.
7. **Saving:** Press **`Q`** to exit.
8. **Result:** A file named `data/engagement_data.csv` will be created with hundreds of data points.

---

## Phase 4: Training the Custom Deep Learning Model
*Status: [COMPLETED]*

**What we built:**
`src/training/train.py` — reads `data/engagement_data.csv` and trains a **Multi-Layer Perceptron (MLP)** in PyTorch to classify if a person is "Engaged" or "Away" based on Yaw, Pitch, and Distance. Data augmentation automatically generates synthetic far-distance samples so the model works at 3–4m range.

### HOW TO ADD NEW TRAINING DATA (New faces / sessions):
> ⚠️ **Never delete `data/engagement_data.csv`** — all scripts append to it, never overwrite.

**Option A — Live training inside the main system (recommended, handles far distances best):**
1. Run `python src/inference/main.py`
2. Click the video window and press **`T`** to toggle Training Mode (green bar appears at bottom)
3. Press **`L`** = LOOK, **`A`** = AWAY
4. Press **`Q`** to quit — data is automatically appended to the CSV

**Option B — Standalone collector:**
```bash
python src/training/data_collector.py
```

**After collecting, always re-train:**
```bash
python src/training/train.py
```
Output: `models/engagement_model.pth` — the AI brain used by the live system.

---

## Phase 5: Full Live Inference System
*Status: [COMPLETED]*

**What we built:**
`src/inference/main.py` — the complete 5-layer pipeline:

| Layer | Technology | Role |
|---|---|---|
| 1 | YOLOv8 | Detects and tracks each person by unique ID |
| 2 | MediaPipe FaceLandmarker | Extracts Yaw, Pitch, Distance from head pose |
| 3 | PyTorch MLP | Classifies Engaged vs. Away |
| 4 | Store Config | Defines physical engagement zone boundaries |
| 5 | Analytics HUD | Shows live metrics on screen + writes to dashboard |

### HOW TO RUN THE FULL SYSTEM:
```bash
# Terminal 1 — Dashboard web server
python -m http.server 8080

# Terminal 2 — AI engine
.\venv\Scripts\Activate.ps1
python src/inference/main.py
```
Then open **`http://localhost:8080/dashboard.html`** in your browser.

**Controls inside the video window:**

| Key | Action |
|---|---|
| `T` | Toggle Training Mode on/off |
| `L` | (Training Mode) Save LOOK sample |
| `A` | (Training Mode) Save AWAY sample |
| `Q` | Quit and save any training data |

---

## Phase 6: Second-Pass False Positive Filters
*Status: [COMPLETED — 2026-04-15]*

**The problem:** YOLOv8 occasionally detects chairs, bags, or furniture as "people", inflating the passersby count.

**What we built:** A 3-gate second-pass verification system in `main.py`. Every YOLO detection must pass all 3 gates before being treated as a real person:

### Gate 1 — YOLO Confidence Threshold
```python
YOLO_CONF_MIN = 0.45
```
Any detection YOLO itself is less than 45% confident about is immediately discarded. Displayed on screen as `LOW CONF (XX%)`.

### Gate 2 — Aspect Ratio Filter
```python
ASPECT_RATIO_MIN = 0.75
```
Checks `bounding box height / width`. People are taller than wide. Chairs, tables and furniture are typically wider than tall and are rejected. Displayed as `NOT HUMAN (shape)`.

### Gate 3 — Ghost Track Blacklist
```python
GHOST_FRAME_TRIAL = 20
```
If a track ID is detected for 20 frames but MediaPipe **never** finds a face in the head crop region → it's permanently added to the `ghost_ids` blacklist. The passersby counter is corrected (−1). Displayed as `GHOST (no face)`.

### Tuning the filters:
| Symptom | Fix |
|---|---|
| Real person far away gets ghosted too fast | Increase `GHOST_FRAME_TRIAL` to 30–40 |
| Chairs still slip through | Lower `ASPECT_RATIO_MIN` to 0.6 |
| Too many low-conf rejections | Lower `YOLO_CONF_MIN` to 0.35 |

### How to test the filters:
1. Run `python src/inference/main.py`
2. Place a chair (or bag) in front of the camera — it should show `NOT HUMAN (shape)` or `GHOST (no face)` in grey, not a green/grey person box
3. Check the `Total Passersby` count — it should NOT increment for the chair
4. Walk in front of the camera yourself — you should get a normal coloured box with `ID:X ENGAGED/AWAY`

---

## Phase 7: Torso Angle Compensation
*Status: [COMPLETED — 2026-04-15]*

**The problem:** (Professor Feedback #4) If a person walks past the display sideways but turns their head 90 degrees to glance at it, the system might count this as "Engagement" even though they are just walking past. We need to distinguish between someone *standing* and looking versus someone *walking* and glancing.

**What we built:**
We added the **MediaPipe PoseLandmarker** to calculate the body's orientation.
- The system extracts the LEFT and RIGHT shoulder landmarks for each detected person.
- If the shoulders are wide apart on the camera, the person's torso is facing the display (`Torso = 100%`).
- If the shoulders are closely aligned (side profile), the person is standing sideways (`Torso = 0%`).

**How it works:**
The "Torso Confidence" percentage acts as a multiplier on the PyTorch engagement probability. If a person's body is fully sideways, their head-gaze probability is sliced in half — effectively preventing them from triggering "ENGAGED" status while walking past.

---

## 🔮 Future Vision: Planogram Heatmapping (Product-Level Analytics)
*Concept for future development beyond current scope*

Currently, the AI detects **IF** a person is engaged with the overall display. The holy grail for retailers (including supermarkets) is knowing **WHERE** exactly the person is looking (e.g., "Top Right Shelf" vs "Bottom Center").

**Why not just track eyeballs?**
Tracking actual pupils/irises is impossible at 3–5 meter store distances with standard cameras because the human eye is only 3–5 pixels wide. True eye-tracking requires physical PTZ (Pan-Tilt-Zoom) cameras that automatically optical-zoom into faces.

**The Solution: 3D Raycasting (Professor Feedback #3: Projective Perspective)**
Instead of tracking eyeballs, the industry standard is to use head angle vectoring combined with 3D store geometry:
1. **Map:** Define the physical dimensions of the vitrina/shelves in a 3D coordinate grid.
2. **Locate:** Use the camera to locate exactly where the person is standing on the floor plan relative to the display.
3. **Raycast:** Take the Pitch/Yaw we already calculate and project an invisible "laser" out from the person's face.
4. **Intersect:** Calculate exactly where that 3D laser intersects with the 2D plane of the shelves.
5. **Heatmap:** Aggregate these intersections over time to show exactly which physical products attract the most attention.

---

## ⚖️ GDPR & Data Privacy (Legal Compliance)
*Important notes based on European Data Protection regulations (RGPD/GDPR)*

VisionMetrics is designed fundamentally around **Privacy by Design**. Because camera-based behavior analysis touches upon automated processing and profiling, we adhere strictly to the "Safe Legal Model".

**How our code complies natively:**
1. **No Image Storage (Edge Processing):** 
   - We process the video feed in real-time in RAM (`main.py`). The frames are immediately discarded. We never save `.jpg` or `.mp4` files of the public to the hard drive.
2. **Absolute Anonymity (Temporal Tracking):**
   - YOLO assigns a random number (e.g., `ID: 23`) to track a body while it is on screen.
   - Once the person leaves the camera frame, that ID is destroyed. It is never logged to a file or sent to a database. We cannot retroactively see what "ID 23" did.
3. **Pure Metric Aggregation:**
   - The only data exposed to the Dashboard (`data/live_stats.json`) are completely anonymous sums: `Total Passersby` and `Total Attention Time`. Individual rows of behavior are never retained.
4. **No Automated Decisions Affecting Users:**
   - The system passively collects aggregate metrics for the retailer. It does not alter the physical environment or deny services based on the individual's behavior (we removed dynamic discount QR codes specifically to avoid Article 22 "Automated Individual Decision-making" issues).

**Requirements for Deployment (Transparency):**
If this system is tested in a real public retail environment, a physical warning sign is required at the store entrance (e.g., *"System of visual attention analysis in use. Only anonymous, aggregated data is processed. No images are identifiable or stored."*)
