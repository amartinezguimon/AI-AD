# src/ — LEGACY prototype (frozen)

> ⚠️ This is the original university-project prototype. It still runs, but it is
> **frozen** and being replaced by the productized code under
> [`../visionmetrics/`](../visionmetrics/README.md). See [`../ROADMAP.md`](../ROADMAP.md).

Kept as a reference and as the still-working demo until the new edge agent is
verified end-to-end against real camera footage. Do not build new features here.

| Legacy file | Replacement (or planned home) |
|---|---|
| `inference/main.py` | `visionmetrics/edge/agent/` (pipeline + service) — **done** |
| `inference/detect.py` | `visionmetrics/edge/agent/vision/detector.py` — done |
| `utils/calibrate.py` | `visionmetrics/edge/calibrate.py` (writes device.yaml) — planned |
| `training/train.py`, `train_report.py`, `data_collector.py` | `visionmetrics/ml/` — planned |
| `utils/check_cameras.py` | small utility, migrate as needed |

Run the legacy prototype (unchanged):

```bash
python src/inference/main.py
```
