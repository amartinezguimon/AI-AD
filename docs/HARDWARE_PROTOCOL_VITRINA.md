# Hardware & Setting Protocol: Any Display / Vitrina
## Architecture: Universal AI Brain + Per-Store Config

---

## Core Design Principle (Why This Scales)

This system separates responsibility into two independent layers:

| Layer | File | Changes between stores? |
|---|---|---|
| **Universal AI Brain** | `models/engagement_model.pth` | ❌ Never. Train once. |
| **Store Configuration** | `configs/store_config.json` | ✅ Yes. 60-second calibration per store. |

The AI brain is trained ONCE on diverse human head movements. It outputs precise 
normalised angles (Yaw, Pitch) and a Distance proxy, regardless of who the person is,
how tall they are, or how far away the camera is. 

The store configuration defines the PHYSICAL BOUNDARY of the display — left edge, 
right edge, center pitch, and the valid distance range — expressed in those same 
normalised angles. The final inference engine simply checks: "do the AI's angles 
fall inside the store's boundary box?"

---

## Step 1: Physical Camera Placement

**This is THE most important decision. Once the camera is placed and calibrated, 
you CANNOT move it without recalibrating.**

### Recommended Placement: Eye-Level Center
- Mount the camera at the **horizontal center** of the display.
- Mount it at **eye-level** or slightly above (1.4 - 1.7m height).
- The camera should point **straight out**, perpendicular to the display surface.
- Use a tripod, wall bracket, or suction mount.

### What Camera to Use
| Option | Quality | Range | Setup |
|---|---|---|---|
| iPhone (via Iriun/Camo) | ⭐⭐⭐⭐⭐ | Up to 4m | Download Iriun app, connect via Wi-Fi |
| USB Webcam (Logitech C920) | ⭐⭐⭐⭐ | Up to 3m | Plug in USB |
| Laptop Webcam | ⭐⭐ | Up to 1.5m | No setup needed |

**To use iPhone:** Change `CAMERA_INDEX = 0` to `CAMERA_INDEX = 1` in both 
`data_collector.py` and `calibrate.py`.

---

## Step 2: Collect Universal Training Data

Run this ONCE (or multiple times to accumulate more data):
```bash
python src/training/data_collector.py
```

### The Diversity Protocol (Critical for scalability)
The goal is to teach the AI what "looking forward" means across many different 
scenarios. Do NOT target a specific vitrina — just look at the CAMERA.

| Session | What to do | Key | Reps |
|---|---|---|---|
| Close, straight | 0.5m away, look at camera | L | 10 |
| Close, slight left | 0.5m away, look slightly left of camera | L | 5 |
| Close, slight right | 0.5m away, look slightly right of camera | L | 5 |
| Medium, straight | 1.0m away, look at camera | L | 10 |
| Medium, slight angles | 1.0m, look left/right slightly | L | 10 |
| Far, straight | 2.0m away, look at camera | L | 10 |
| Tall person (teammate) | Any distance, different team member | L | 15 |
| Short/crouching | Crouch down to simulate shorter person | L | 10 |
| **Away: Phone** | Look down at phone | A | 15 |
| **Away: Sideways** | Turn head 90° like talking to someone | A | 15 |
| **Away: Walking** | Walk past the camera looking ahead | A | 15 |
| **Away: Ceiling** | Look up at ceiling | A | 10 |

Target: ~100 LOOK rows and ~100 AWAY rows minimum.

---

## Step 3: Train the Universal AI Brain

After collecting data:
```bash
python src/training/train.py
```
This reads `data/engagement_data.csv` and produces `models/engagement_model.pth`.
This file is the "Universal Brain" and does NOT need to be retrained per store.

---

## Step 4: Calibrate Each New Store (60 seconds per store)

With the camera mounted and the display in view:
```bash
python src/utils/calibrate.py
```

Follow the on-screen instructions:
1. Stand in front of the display. Look at the **far LEFT edge** → press `1`
2. Look at the **CENTER** of the display → press `2`
3. Look at the **far RIGHT edge** → press `3`
4. Stand as **CLOSE** as a customer ever gets → press `4`
5. Stand as **FAR** as a customer ever gets → press `5`
6. Press `S` to save.

This creates `configs/store_config.json` — a file unique to that installation.

---

## Step 5: Run the Live System

```bash
python src/inference/main.py
```

The system will:
1. Load the Universal AI Brain (`models/engagement_model.pth`)
2. Load the Store Config (`configs/store_config.json`)
3. Open the camera and begin tracking in real time
4. Log analytics to `data/session_log.csv`
5. Trigger the "live reward" (QR code overlay) when engagement threshold is met

---

## Notes on Different Display Types

| Display Type | Expected Yaw Range | Notes |
|---|---|---|
| Small poster (A2) | ±0.05 | Very narrow — camera must be centered |
| Standard vitrina (1.5m) | ±0.30 | Normal retail case |
| Wide vitrina (2.5m+) | ±0.50 | Expect more misses at the edges |
| Full shop window | ±0.70 | Very wide — may need 2 cameras |

For very wide displays, consider mounting **two cameras** at the left and right thirds,
each with its own `store_config.json`, and merging their analytics outputs.
