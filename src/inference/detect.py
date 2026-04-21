import cv2
from ultralytics import YOLO

# --- Step 1: Load the AI Brain ---
# We are downloading a pre-trained YOLOv8 nano model (the fastest version).
# It has already been trained on millions of images to recognize 80 different things (including people).
print("Loading YOLOv8 AI model...")
model = YOLO('yolov8n.pt') 

# --- Step 2: Open your Webcam ---
# The number 0 usually means "Use the default laptop webcam".
# If you have a USB camera plugged in, it might be 1 or 2.
print("Connecting to the webcam...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Camera is active! Press the 'q' key on your keyboard to close the window.")

# --- Step 3: The Video Loop ---
# A video is just a lot of pictures (frames) shown very fast.
# We create a loop to look at the camera feed frame-by-frame forever.
while True:
    # Grab the current picture from the camera
    success, frame = cap.read()
    
    if not success:
        print("Failed to grab frame. Exiting...")
        break

    # --- Step 4: AI Analysis ---
    # We hand the picture over to the YOLO AI.
    # 'classes=[0]' tells the AI: "Only look for Class 0 (which is 'person'). Ignore dogs, cars, etc."
    # 'verbose=False' tells the AI to shut up and not print debug text constantly.
    results = model(frame, classes=[0], verbose=False)

    # The AI gives back the picture, but it drew boxes around people.
    # We grab that modified picture.
    annotated_frame = results[0].plot()

    # --- Step 5: Show the Picture to the User ---
    # Open a popup window called "VisionMetrics"
    cv2.imshow("VisionMetrics - Person Detection Prototype", annotated_frame)

    # --- Step 6: Wait for Quit Command ---
    # Wait 1 millisecond for the user to press a key.
    # If the key they pressed is 'q', break the infinite loop.
    if cv2.waitKey(1) & 0xFF == ord("q"):
        print("User pressed 'q'. Quitting...")
        break

# --- Cleanup ---
# Once the loop breaks, we must politely turn off the camera hardware and destroy the popup.
cap.release()
cv2.destroyAllWindows()
print("Process finished successfully.")
