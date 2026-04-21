# AI/ML Analytics: Project VisionMetrics
## 📈 Project Guidelines & Feasibility Study

> [!IMPORTANT]
> **Deadline:** April 28, 2026.
> **Deliverables:** Executive Report (35%), Prototype & Code Repo (40%), Presentation (25%).

## 1. Project Overview: "Privacy-Preserving Ad Engagement Analytics"
The goal is to provide digital-style metrics for physical advertisements using computer vision.
- **Problem:** Physical ads, specifically wide display cases like a **Jewelry Stand ("Vitrina")**, lack precise engagement and gaze data. 
- **Solution:** A camera-based system using Edge-AI (via smartphone/tripod setups) to track pass-bys, dwell time, and horizontal gaze tracking simulating a wide customer engagement zone (0.5m-2.0m).
- **NOVELTY:** If the system detects a viewer deeply engaged with the Vitrina for > 5 seconds, it triggers a live interaction (e.g., a QR code display for a discount or salesperson notification).
- **Privacy:** Real-time processing only. No facial identity stored.

## 2. Technical Roadmap (Prototype)
We will build a modular system separated by training and inference to meet the instructor's requirements.
- **Vision Backbone:** YOLOv8 (person detection + tracking) and MediaPipe (head-pose extraction).
- **Custom Deep Learning (Training):** We will train our own PyTorch Neural Network on curated data to classify "Engaged" vs "Not Engaged" using extracted facial angles. This fulfills the requirement for a separate training component.
- **Interactive Trigger:** Logic that "Talks Live" to the user when engagement thresholds are met.
- **Metric Aggregation:** Process raw frames into temporal metrics (Total Pass-bys, Gaze Time, 'Reward' pickups).

## 3. Feasibility Analysis
- **Technical:** High. Pre-trained models are available for both person detection and gaze.
- **Economic:** Strong value proposition. Low hardware cost (Raspberry Pi/Camera).
- **Market:** Significant opportunity in the Retail and OOH (Out-of-Home) advertising sectors.

## 4. Workload Strategy
- **Research & Data:** Collecting validation samples (+ metrics justification).
- **Back-end/ML:** Implementing the detection and logic.
- **Business/Reporting:** Executive report (5000 words on viability and design).

---
*Created by AI Antigravity for the Final Project.*
