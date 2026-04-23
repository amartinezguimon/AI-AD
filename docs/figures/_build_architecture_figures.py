"""
Builds block-diagram figures for the executive report:
- architecture.png : end-to-end system (camera -> inference -> 3 outputs)
- pipeline.png    : per-frame 7-stage pipeline

Pure matplotlib. Keep the code readable so diagrams can be tweaked later.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

FIG_DIR = "docs/figures"
os.makedirs(FIG_DIR, exist_ok=True)


def box(ax, xy, w, h, text, fc="#e8eef7", ec="#1f4e79", fontsize=9, fontweight="normal"):
    x, y = xy
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                 fc=fc, ec=ec, lw=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight=fontweight)


def arrow(ax, xy1, xy2, color="#333"):
    ax.add_patch(FancyArrowPatch(xy1, xy2, arrowstyle="-|>", mutation_scale=12,
                                  color=color, lw=1.1))


# ── Figure 1 : System architecture ───────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))
ax.set_xlim(0, 12); ax.set_ylim(0, 6)
ax.axis("off")

# Input
box(ax, (0.2, 2.5), 1.8, 1.0, "USB webcam\n/ phone camera\n(Camo Studio)", fc="#fff0d9", ec="#b5651d")

# Core inference block
box(ax, (2.6, 0.8), 4.8, 4.4, "", fc="#f4f7fc", ec="#1f4e79")
ax.text(5.0, 5.0, "On-device inference (main.py)", ha="center", fontsize=10, fontweight="bold", color="#1f4e79")

box(ax, (2.8, 3.9), 2.0, 0.7, "YOLOv8n\nperson tracker", fontsize=8)
box(ax, (5.0, 3.9), 2.2, 0.7, "MediaPipe Face\n(cheekbone yaw)", fontsize=8)
box(ax, (2.8, 3.0), 2.0, 0.7, "MediaPipe Pose\n(torso confidence)", fontsize=8)
box(ax, (5.0, 3.0), 2.2, 0.7, "PyTorch MLP\n(3→16→8→1)", fontsize=8)
box(ax, (2.8, 2.1), 4.4, 0.7, "Soft zone filter (yaw × pitch × distance)  ⊗  torso weight  ⊗  frame buffer (3 frames)", fontsize=8)
box(ax, (2.8, 1.1), 4.4, 0.7, "Per-person state: last_prob, total_engage_s, counted_as_engaged, qr_active_until", fontsize=8)

# Outputs
box(ax, (8.0, 4.3), 3.7, 0.9, "Operator window (OpenCV)\ntier label · duration ring · gaze arrow", fc="#e7f4e4", ec="#2b7a2b", fontsize=8)
box(ax, (8.0, 3.0), 3.7, 0.9, "Customer ad screen (ad_screen.html)\nQR fades in on engagement ≥ 5 s", fc="#e7f4e4", ec="#2b7a2b", fontsize=8)
box(ax, (8.0, 1.7), 3.7, 0.9, "Manager dashboard (dashboard.html)\nlive KPIs, hourly bars, weekly compare", fc="#e7f4e4", ec="#2b7a2b", fontsize=8)

# Data layer
box(ax, (2.6, 0.1), 9.1, 0.55, "data/live_stats.json  ·  hourly_log.json  ·  session_history.json  (writes only — no cloud by default)",
    fc="#fce9d6", ec="#b5651d", fontsize=8)

# Arrows
arrow(ax, (2.0, 3.0), (2.8, 3.3))
arrow(ax, (7.2, 4.0), (8.0, 4.7))
arrow(ax, (7.2, 3.2), (8.0, 3.4))
arrow(ax, (7.2, 2.4), (8.0, 2.1))

plt.title("VisionMetrics AI — on-device retail engagement system")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/architecture.png", dpi=140); plt.close()


# ── Figure 2 : Per-frame pipeline (sequence) ─────────────────
fig, ax = plt.subplots(figsize=(11, 3.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 3.0)
ax.axis("off")

stages = [
    ("1. Capture", "BGR frame\n(newest, thread-drained)"),
    ("2. YOLOv8n", "persons, tracks,\nbboxes (conf≥0.45)"),
    ("3. Head crop + 4× upscale", "top 45% of bbox,\n+30 px padding"),
    ("4. MediaPipe Face", "yaw (cheekbones)\npitch (nose-top/chin)"),
    ("5. MediaPipe Pose", "torso span,\nrel-yaw neck-vs-torso"),
    ("6. MLP & zone filter", "p_engage × torso × zone"),
    ("7. Aggregate", "buffer(3), counters,\nqr_active_until"),
]

w = 1.45; gap = 0.18
for i, (title, body) in enumerate(stages):
    x = 0.3 + i * (w + gap)
    ax.add_patch(FancyBboxPatch((x, 0.9), w, 1.3, boxstyle="round,pad=0.02",
                                 fc="#eef2fa", ec="#1f4e79", lw=1.2))
    ax.text(x + w / 2, 1.75, title, ha="center", va="center",
            fontsize=8.5, fontweight="bold", color="#1f4e79")
    ax.text(x + w / 2, 1.2, body, ha="center", va="center", fontsize=7.8)
    if i < len(stages) - 1:
        ax.add_patch(FancyArrowPatch((x + w, 1.55), (x + w + gap, 1.55),
                                      arrowstyle="-|>", mutation_scale=10, color="#555", lw=0.9))

ax.text(6.0, 0.4, "Skip-frame caches: MediaPipe Face every 3 frames · Pose every 8 frames · per-person ghost blacklist after 20 frames without face",
        ha="center", va="center", fontsize=8, color="#555")
plt.title("Per-frame processing pipeline (main.py)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/pipeline.png", dpi=140); plt.close()


# ── Figure 3 : Zone heatmap concept ──────────────────────────
# A synthetic engagement heatmap over a 20x20 (yaw,pitch) grid,
# used in the report to illustrate "where do customers look on the
# showcase". Built from a Gaussian centred slightly left-of-centre.
import numpy as np
xs = np.linspace(-0.4, 0.4, 40)
ys = np.linspace(-0.3, 0.3, 30)
X, Y = np.meshgrid(xs, ys)
# Two attention hotspots (left-centre and slightly below centre)
Z = 0.75 * np.exp(-((X + 0.12) ** 2 / 0.018 + (Y - 0.02) ** 2 / 0.014)) \
  + 0.55 * np.exp(-((X - 0.08) ** 2 / 0.02 + (Y + 0.05) ** 2 / 0.016)) \
  + 0.1
fig, ax = plt.subplots(figsize=(6.5, 3.8))
im = ax.imshow(Z, extent=[-0.4, 0.4, -0.3, 0.3], origin="lower",
               cmap="hot", aspect="auto")
plt.colorbar(im, ax=ax, label="relative dwell time")
ax.set_xlabel("yaw (left ← → right)")
ax.set_ylabel("pitch (down ← → up)")
ax.set_title("Illustrative showcase gaze heatmap (synthetic example)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/gaze_heatmap_example.png", dpi=140); plt.close()

print("Architecture & pipeline figures saved.")
