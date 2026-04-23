"""
train.py — PyTorch MLP Training Script
---------------------------------------
Trains a binary engagement classifier on labelled head-pose data.

Inputs  : data/engagement_data.csv  (columns: yaw, pitch, distance, label)
Output  : models/engagement_model.pth

Architecture : 3 -> 16 -> 8 -> 1  (ReLU activations, Sigmoid output)
Loss         : Binary Cross Entropy
Optimiser    : Adam (lr=0.005, 50 epochs, batch size 8)

Data strategy:
    Real rows are split BEFORE augmentation to prevent leakage.
    Augmentation generates synthetic far-distance samples by scaling the
    distance column (x0.6, x0.35, x0.15) on training rows only.

HOW TO RUN:
    python src/training/train.py
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split

# ─────────────────────────────────────────────
# 1. DEFINE THE DATASET CLASS
# ─────────────────────────────────────────────
class EngagementDataset(Dataset):
    def __init__(self, features, labels):
        # Convert data to PyTorch tensors (the format the AI needs)
        self.X = torch.tensor(features, dtype=torch.float32)
        
        # Labels must be shaped as a column (N, 1) for PyTorch
        self.y = torch.tensor(labels, dtype=torch.float32).view(-1, 1)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# ─────────────────────────────────────────────
# 2. DEFINE THE NEURAL NETWORK ARCHITECTURE
# ─────────────────────────────────────────────
class EngagementNet(nn.Module):
    """
    Multi-Layer Perceptron for binary engagement classification.
    Input:  3 features (yaw, pitch, normalised face width as distance proxy)
    Output: scalar in [0, 1] — probability that the person is engaged
    """
    def __init__(self):
        super(EngagementNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(3, 16),      # input layer
            nn.ReLU(),
            nn.Linear(16, 8),      # hidden layer
            nn.ReLU(),
            nn.Linear(8, 1),       # output layer
            nn.Sigmoid()           # squashes output to [0, 1] probability
        )

    def forward(self, x):
        return self.network(x)

# ─────────────────────────────────────────────
# 3. MAIN TRAINING LOOP
# ─────────────────────────────────────────────
def train_model():
    csv_path = "data/engagement_data.csv"
    model_path = "models/engagement_model.pth"

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run data_collector.py first.")
        return

    print("\nLoading data...")
    df = pd.read_csv(csv_path).dropna()
    print(f"Valid samples: {len(df)}")
    print(df['label'].value_counts())

    X = df[['yaw', 'pitch', 'distance']].values
    y = df['label'].values

    import numpy as np

    # ── SPLIT REAL DATA FIRST, then augment only the training portion ──
    # IMPORTANT: Augmentation must happen AFTER the test split.
    # If we augment first, the same yaw/pitch values (with only a scaled
    # distance) appear in both train and test, making the test set trivially
    # easy and inflating accuracy. Holding out real rows first prevents this.
    X_real_tr, X_test, y_real_tr, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── DATA AUGMENTATION: Synthetic Far-Distance Samples (train only) ──
    # KEY INSIGHT: Yaw and Pitch are normalised (scale-invariant).
    # A person looking straight at 0.5m gives the same Yaw ~0 as at 4m.
    # Only the distance proxy (normalised face width) changes.
    # We generate realistic far-distance examples by scaling the distance
    # column. This is called Domain Randomisation in ML literature.
    augmented_X = []
    augmented_y = []
    for row, label in zip(X_real_tr, y_real_tr):
        yaw, pitch, dist = row
        for scale in [0.6, 0.35, 0.15]:   # roughly 1.5m, 2.5m, 4m
            noise = np.random.normal(0, 0.005, size=2)
            augmented_X.append([yaw + noise[0], pitch + noise[1], dist * scale])
            augmented_y.append(label)

    aug_X = np.array(augmented_X)
    aug_y = np.array(augmented_y)

    X_train = np.vstack([X_real_tr, aug_X])
    y_train = np.concatenate([y_real_tr, aug_y])

    print(f"Original samples: {len(X)}  |  Test (real only): {len(X_test)}  |  Train after augmentation: {len(X_train)}")


    train_dataset = EngagementDataset(X_train, y_train)
    test_dataset  = EngagementDataset(X_test, y_test)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

    print("\nInitialising network...")
    model = EngagementNet()
    loss_function = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.005)

    epochs = 50
    print("Training...")
    print("-" * 50)
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch_x, batch_y in train_loader:
            predictions = model(batch_x)
            loss = loss_function(predictions, batch_y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}]  loss: {total_loss/len(train_loader):.4f}")

    # Evaluate on the held-out real test set
    model.eval()
    with torch.no_grad():
        test_inputs  = torch.tensor(X_test, dtype=torch.float32)
        test_answers = torch.tensor(y_test, dtype=torch.float32).view(-1, 1)
        predictions  = model(test_inputs)
        correct      = (predictions.round() == test_answers).sum().item()
        accuracy     = (correct / len(y_test)) * 100

    print("-" * 50)
    print(f"Test accuracy (real rows only): {accuracy:.2f}%")

    os.makedirs("models", exist_ok=True)
    torch.save(model.state_dict(), model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_model()
