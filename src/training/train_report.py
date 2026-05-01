"""
train_report.py — same training run as train.py, but emits artefacts for the
executive report: loss/accuracy curves, confusion matrix, classification report,
ROC curve, per-distance-bucket accuracy, and a logistic-regression baseline.

Run:
    python src/training/train_report.py

Outputs (all under figures/):
    train_curves.png
    confusion_matrix.png
    roc_curve.png
    per_distance_accuracy.png
    metrics.json
    classification_report.txt
"""

import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix, classification_report,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIG_DIR = "figures"
CSV_PATH = "data/engagement_data.csv"
MODEL_PATH = "models/engagement_model.pth"
SEED = 42
EPOCHS = 50
LR = 0.005
BATCH = 8


class EngagementNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(3, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 1),  nn.Sigmoid(),
        )

    def forward(self, x):
        return self.network(x)


class EngagementDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).view(-1, 1)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def augment(X, y, scales=(0.6, 0.35, 0.15), noise_std=0.005, seed=SEED):
    rng = np.random.default_rng(seed)
    rows_x, rows_y = [], []
    for (yaw, pitch, dist), label in zip(X, y):
        for s in scales:
            n = rng.normal(0, noise_std, 2)
            rows_x.append([yaw + n[0], pitch + n[1], dist * s])
            rows_y.append(label)
    return np.array(rows_x), np.array(rows_y)


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    torch.manual_seed(SEED); np.random.seed(SEED)

    df = pd.read_csv(CSV_PATH).dropna()
    print(f"Loaded {len(df)} real rows | label counts: {df['label'].value_counts().to_dict()}")

    X = df[["yaw", "pitch", "distance"]].values
    y = df["label"].values.astype(np.int64)

    # ── Hold out 20% of REAL rows first, THEN augment only the remaining 80%.
    # This avoids leakage (same yaw/pitch showing up in train and test with
    # only a scaled distance — which trivially inflates accuracy to 100%).
    X_real_tr, X_test, y_real_tr, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )
    aug_X, aug_y = augment(X_real_tr, y_real_tr)
    X_train = np.vstack([X_real_tr, aug_X])
    y_train = np.concatenate([y_real_tr, aug_y])
    print(f"Real rows held out for test: {len(X_test)}")
    print(f"Training rows after 3x augmentation on train-only: {len(X_train)}")

    # sub-split training into train/val for curves
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=SEED, stratify=y_train
    )

    loader = DataLoader(EngagementDataset(X_tr, y_tr), batch_size=BATCH, shuffle=True)

    net = EngagementNet()
    loss_fn = nn.BCELoss()
    optim_ = optim.Adam(net.parameters(), lr=LR)

    tr_losses, val_losses, val_accs = [], [], []

    for epoch in range(EPOCHS):
        net.train()
        running = 0.0
        for bx, by in loader:
            optim_.zero_grad()
            p = net(bx); l = loss_fn(p, by)
            l.backward(); optim_.step()
            running += l.item() * len(bx)
        tr_loss = running / len(X_tr)

        net.eval()
        with torch.no_grad():
            v_pred = net(torch.tensor(X_val, dtype=torch.float32))
            v_true = torch.tensor(y_val, dtype=torch.float32).view(-1, 1)
            v_loss = loss_fn(v_pred, v_true).item()
            v_acc = ((v_pred.round() == v_true).float().mean().item())
        tr_losses.append(tr_loss); val_losses.append(v_loss); val_accs.append(v_acc)
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1:>2} | train loss {tr_loss:.4f} | val loss {v_loss:.4f} | val acc {v_acc:.3f}")

    # ── Test set evaluation ───────────────────────
    net.eval()
    with torch.no_grad():
        probs = net(torch.tensor(X_test, dtype=torch.float32)).numpy().ravel()
    preds = (probs >= 0.5).astype(int)

    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds)
    rec = recall_score(y_test, preds)
    f1 = f1_score(y_test, preds)
    auc = roc_auc_score(y_test, probs)
    cm = confusion_matrix(y_test, preds)

    print("\n-- MLP test metrics --")
    print(f"Accuracy : {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1       : {f1:.4f}")
    print(f"ROC-AUC  : {auc:.4f}")
    print(f"CM       : {cm.tolist()}")

    # ── Baselines ────────────────────────────────
    # (a) Yaw-threshold rule: predict "engaged" if |yaw| < 0.10
    yaw_rule_pred = (np.abs(X_test[:, 0]) < 0.10).astype(int)
    acc_yaw = accuracy_score(y_test, yaw_rule_pred)
    f1_yaw = f1_score(y_test, yaw_rule_pred, zero_division=0)

    # (b) Logistic regression on same 3 features
    logreg = LogisticRegression(max_iter=500).fit(X_tr, y_tr)
    lr_pred = logreg.predict(X_test)
    lr_prob = logreg.predict_proba(X_test)[:, 1]
    acc_lr = accuracy_score(y_test, lr_pred)
    f1_lr = f1_score(y_test, lr_pred)
    auc_lr = roc_auc_score(y_test, lr_prob)

    # ── Per-distance bucket accuracy ─────────────
    dist = X_test[:, 2]
    buckets = [("near (dist>0.35)", dist > 0.35),
               ("mid  (0.15<=d<=0.35)", (dist >= 0.15) & (dist <= 0.35)),
               ("far  (dist<0.15)", dist < 0.15)]
    per_bucket = []
    for name, mask in buckets:
        if mask.sum() == 0:
            per_bucket.append((name, 0, 0.0))
            continue
        per_bucket.append((name, int(mask.sum()), accuracy_score(y_test[mask], preds[mask])))

    # ── Plot loss/acc curves ─────────────────────
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(range(1, EPOCHS + 1), tr_losses, label="train loss", color="#1f77b4")
    ax1.plot(range(1, EPOCHS + 1), val_losses, label="val loss", color="#ff7f0e")
    ax1.set_xlabel("epoch"); ax1.set_ylabel("BCE loss"); ax1.grid(alpha=0.3)
    ax2 = ax1.twinx()
    ax2.plot(range(1, EPOCHS + 1), val_accs, linestyle="--", color="#2ca02c", label="val accuracy")
    ax2.set_ylabel("validation accuracy")
    ax1.legend(loc="upper right"); ax2.legend(loc="lower right")
    plt.title("EngagementNet — training / validation curves")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/train_curves.png", dpi=130); plt.close()

    # ── Confusion matrix plot ────────────────────
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, cmap="Blues"); plt.colorbar(im, ax=ax)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["Away", "Engaged"]); ax.set_yticklabels(["Away", "Engaged"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=14)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    plt.title("EngagementNet confusion matrix (test set)")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/confusion_matrix.png", dpi=130); plt.close()

    # ── ROC curve plot ───────────────────────────
    fpr, tpr, _ = roc_curve(y_test, probs)
    fpr_lr, tpr_lr, _ = roc_curve(y_test, lr_prob)
    plt.figure(figsize=(5.5, 5))
    plt.plot(fpr, tpr, label=f"MLP (AUC={auc:.3f})", color="#1f77b4", lw=2)
    plt.plot(fpr_lr, tpr_lr, label=f"LogReg baseline (AUC={auc_lr:.3f})", color="#ff7f0e", lw=1.5, linestyle="--")
    plt.plot([0, 1], [0, 1], color="gray", linestyle=":", label="random")
    plt.xlabel("false positive rate"); plt.ylabel("true positive rate")
    plt.title("ROC — MLP vs logistic-regression baseline")
    plt.legend(loc="lower right"); plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/roc_curve.png", dpi=130); plt.close()

    # ── Per-distance bar ─────────────────────────
    labels = [b[0] for b in per_bucket]
    accs = [b[2] for b in per_bucket]
    counts = [b[1] for b in per_bucket]
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    bars = ax.bar(labels, accs, color=["#1f77b4", "#2ca02c", "#d62728"])
    ax.set_ylim(0, 1.05); ax.set_ylabel("accuracy")
    for b, c in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"n={c}", ha="center", fontsize=9)
    ax.set_title("Test accuracy by distance bucket (normalised face-width)")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/per_distance_accuracy.png", dpi=130); plt.close()

    # ── Save metrics & classification report ─────
    metrics = {
        "dataset": {
            "real_rows": int(len(X)),
            "augmented_train_rows": int(len(X_train)),
            "train_rows": int(len(X_tr)),
            "val_rows": int(len(X_val)),
            "test_rows": int(len(X_test)),
            "label_counts": {int(k): int(v) for k, v in df["label"].value_counts().items()},
        },
        "mlp": {
            "accuracy": acc, "precision": prec, "recall": rec,
            "f1": f1, "roc_auc": auc, "confusion_matrix": cm.tolist(),
        },
        "baselines": {
            "yaw_threshold_rule": {"accuracy": acc_yaw, "f1": f1_yaw, "threshold": 0.10},
            "logistic_regression": {"accuracy": acc_lr, "f1": f1_lr, "roc_auc": auc_lr},
        },
        "per_distance": [{"bucket": n, "n": c, "accuracy": a} for n, c, a in per_bucket],
        "hyperparameters": {"epochs": EPOCHS, "lr": LR, "batch_size": BATCH, "seed": SEED,
                             "augmentation_scales": [0.6, 0.35, 0.15]},
    }
    with open(f"{FIG_DIR}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(f"{FIG_DIR}/classification_report.txt", "w") as f:
        f.write(classification_report(y_test, preds, target_names=["Away", "Engaged"]))

    # ── Save model ───────────────────────────────
    os.makedirs("models", exist_ok=True)
    torch.save(net.state_dict(), MODEL_PATH)
    print(f"\nArtefacts saved under {FIG_DIR}/")
    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
