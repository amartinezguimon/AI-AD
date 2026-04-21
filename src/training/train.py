"""
train.py — Deep Learning Engine for Engagement Analysis
--------------------------------------------------------------
PURPOSE:
    This script fulfills the core academic requirement of building a
    Custom Deep Learning Model using PyTorch. 
    
    It reads the 'universal' human data we just collected in the CSV, 
    and trains a Multi-Layer Perceptron (Neural Network) to understand
    the mathematical relationship between Yaw, Pitch, and Distance.

HOW TO RUN:
    python src/training/train.py

OUTPUT:
    models/engagement_model.pth  ← This is our "Artificial Brain".
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
    A Deep Neural Network (Multi-Layer Perceptron)
    Input:  3 features (Yaw, Pitch, Distance)
    Output: 1 value between 0 and 1 (Probability of Looking)
    """
    def __init__(self):
        super(EngagementNet, self).__init__()
        
        # Three layers of "Neurons"
        self.network = nn.Sequential(
            nn.Linear(3, 16),      # Input Layer: 3 inputs -> 16 hidden neurons
            nn.ReLU(),             # Activation Function (adds non-linear thinking)
            
            nn.Linear(16, 8),      # Hidden Layer: 16 -> 8 neurons
            nn.ReLU(),
            
            nn.Linear(8, 1),       # Output Layer: 8 -> 1 result
            nn.Sigmoid()           # Forces the final answer to be between 0 (Away) and 1 (Look)
        )

    def forward(self, x):
        return self.network(x)

# ─────────────────────────────────────────────
# 3. MAIN TRAINING LOOP
# ─────────────────────────────────────────────
def train_model():
    csv_path = "data/engagement_data.csv"
    model_path = "models/engagement_model.pth"

    # -- Error Checking --
    if not os.path.exists(csv_path):
        print(f"❌ Error: Cannot find {csv_path}. Please run data_collector.py first.")
        return

    # -- Load the Data using Pandas --
    print("\n📊 Loading data from CSV...")
    df = pd.read_csv(csv_path)
    
    # We drop any rows with NaN just in case the camera glitched
    df = df.dropna()

    print(f"Total valid samples: {len(df)}")
    print(df['label'].value_counts())

    # Separate Features (Inputs) and Labels (Answers)
    X = df[['yaw', 'pitch', 'distance']].values
    y = df['label'].values

    # ── DATA AUGMENTATION: Synthetic Far-Distance Samples ────────
    # KEY INSIGHT: Yaw and Pitch are normalised (scale-invariant).
    # A person looking straight at 0.5m gives the same Yaw ≈ 0 as
    # at 4m. ONLY the 'distance' proxy (face_width) changes.
    #
    # So we can generate realistic "far distance" training examples
    # by simply scaling down the distance column of existing rows.
    # This is called "Domain Randomisation" in ML literature.
    import numpy as np
    augmented_X = []
    augmented_y = []
    for i, row in enumerate(X):
        yaw, pitch, dist = row
        # For each real sample, add 3 synthetic "far away" versions
        for scale in [0.6, 0.35, 0.15]:   # ~1.5m, ~2.5m, ~4m equivalents
            # Add a tiny bit of noise so rows aren't identical
            noise = np.random.normal(0, 0.005, size=2)
            augmented_X.append([yaw + noise[0], pitch + noise[1], dist * scale])
            augmented_y.append(y[i])

    aug_X = np.array(augmented_X)
    aug_y = np.array(augmented_y)

    # Combine real + synthetic data
    X_combined = np.vstack([X, aug_X])
    y_combined  = np.concatenate([y, aug_y])

    print(f"Original samples: {len(X)}  →  After augmentation: {len(X_combined)}")

    # Split into 80% Training Data and 20% Testing Data
    X_train, X_test, y_train, y_test = train_test_split(X_combined, y_combined, test_size=0.2, random_state=42)


    train_dataset = EngagementDataset(X_train, y_train)
    test_dataset  = EngagementDataset(X_test, y_test)

    # DataLoaders pump data into the AI in small batches
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

    # -- Initialize the AI --
    print("\n🧠 Initializing the Neural Network...")
    ai_brain = EngagementNet()
    
    # Standard configuration for Binary Classification (0 or 1)
    loss_function = nn.BCELoss()      # Binary Cross Entropy
    optimizer = optim.Adam(ai_brain.parameters(), lr=0.005)

    # -- The Training Loop --
    epochs = 50
    print("\n🚀 Starting PyTorch Training Process...")
    print("--------------------------------------------------")

    for epoch in range(epochs):
        ai_brain.train()
        total_loss = 0

        for batch_x, batch_y in train_loader:
            # 1. Forward Pass (Ask the AI to guess)
            predictions = ai_brain(batch_x)
            
            # 2. Calculate the Error (How wrong was it?)
            loss = loss_function(predictions, batch_y)
            
            # 3. Backward Pass (Learn from the mistake)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()

        # Print progress every 10 epochs
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}]  --->  Error (Loss): {total_loss/len(train_loader):.4f}")

    # -- Evaluate Accuracy on the Test Set (The 20% it has never seen) --
    ai_brain.eval()
    with torch.no_grad():
        test_inputs = torch.tensor(X_test, dtype=torch.float32)
        test_answers = torch.tensor(y_test, dtype=torch.float32).view(-1, 1)
        
        predictions = ai_brain(test_inputs)
        # If probability is > 50%, we count it as a "Look" (1)
        predictions_rounded = predictions.round() 
        
        correct = (predictions_rounded == test_answers).sum().item()
        accuracy = (correct / len(y_test)) * 100

    print("--------------------------------------------------")
    print(f"🎯 Final AI Accuracy on unseen data: {accuracy:.2f}%")

    # -- Save the Artificial Brain --
    os.makedirs("models", exist_ok=True)
    torch.save(ai_brain.state_dict(), model_path)
    print(f"\n✅ SUCCESS: Artificial Brain trained and safely saved to {model_path}.")
    print("This file can now be used in any store automatically!")

if __name__ == "__main__":
    train_model()
