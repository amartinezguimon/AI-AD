# ⚖️ VisionMetrics AI: Privacy Policy & Data Handling

*This document outlines the strict "Privacy by Design" architecture of VisionMetrics AI to ensure compliance with the European GDPR (RGPD), the upcoming AI Act, and national data protection laws (LOPDGDD).*

## 1. System Classification
VisionMetrics operates fundamentally as an **"Anonymous Real-Time Sensor without Memory"**. 

It is designed to aggregate engagement metrics for physical retail spaces. It is **NOT** a security/CCTV system, and it is **NOT** a targeted advertising system.

## 2. What we DO NOT collect or process
To maintain compliance and reduce legal risk to the absolute minimum, this system explicitly **DOES NOT**:
- ❌ **Save Images or Video:** No `.jpg`, `.mp4`, or any image format of the public space is ever written to disk. The video stream lives strictly in volatile RAM and is destroyed frame-by-frame.
- ❌ **Process Biometric Identity:** We use MediaPipe to extract structural 3D landmarks (shoulder span, nose tip) only to calculate angles. We DO NOT run facial recognition (no classification of identity, age, gender, or emotion).
- ❌ **Maintain Individual Histories:** The system does not save behavioral logs tied to an individual. It is impossible to query "What did Person X do?"
- ❌ **Make Automated Decisions:** The AI does not trigger personalized physical changes, deny services, or display targeted rewards based on the individual's behavior (No Article 22 RGPD violations).

## 3. Policy of Anonymization and Tracking
- **Ephemeral Tracking:** YOLOv8 assigns a volatile ID (e.g., `ID:45`) purely for inter-frame stability (so the system doesn't count the same person 10 times in one second).
- **Destruction on Exit:** The millisecond a person leaves the camera frame, their ID and their individual engagement metrics are permanently destroyed from RAM.
- **Aggregation Threshold:** The only data exported from the system (`data/live_stats.json`) are aggregate sums (e.g., `Total Passersby: 120`, `Total Engagement Time: 450s`).

## 4. DPIA (Data Protection Impact Assessment) Checklist
*Because classifying human behavior (even anonymously) constitutes "profiling", a DPIA is required before deployment in a public space.*

If deployed, the operator must ensure:
1. **Physical Transparency:** A clearly visible sign must be placed at the entrance of the camera's FOV stating: *"Artificial vision system in use for aggregate statistical analysis. No images are stored and no individuals are identified."*
2. **Employee Notification:** If deployed in a retail space, all staff must be explicitly informed of the system, as they will inevitably be processed as "passersby".
3. **Edge Processing Only:** The processing device must not stream the raw camera feed to any external cloud server or third-party API. All inference must remain local.
