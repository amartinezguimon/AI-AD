"""
detect.py — Standalone Person Detection Demo
----------------------------------------------
A minimal script that runs YOLOv8n on the webcam feed and draws
bounding boxes around detected persons. Useful for verifying that
the camera and YOLOv8 are working before running the full pipeline.

This script does NOT include head-pose estimation, engagement scoring,
or any analytics. For the full system, run src/inference/main.py.

HOW TO RUN:
    python src/inference/detect.py

CONTROLS:
    Q  —  quit
"""

import cv2
from ultralytics import YOLO

# YOLOv8n is auto-downloaded by the ultralytics library on first run.
print("Loading YOLOv8n model...")
model = YOLO('yolov8n.pt')

print("Opening webcam (index 0)...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: could not open webcam.")
    exit()

print("Running. Press Q to quit.")

while True:
    success, frame = cap.read()
    if not success:
        print("Failed to read frame. Exiting.")
        break

    # Run person detection only (class 0 = person in COCO)
    results = model(frame, classes=[0], verbose=False)

    # Annotate frame with bounding boxes
    annotated_frame = results[0].plot()
    cv2.imshow("VisionMetrics — Person Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
