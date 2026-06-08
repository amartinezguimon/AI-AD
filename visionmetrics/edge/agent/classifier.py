"""PyTorch engagement classifier — network definition + loading + scoring.

The architecture MUST stay in lock-step with ml/train.py (3 -> 16 -> 8 -> 1,
Sigmoid). It is defined here once and imported by both the agent and training,
so they can never drift apart.
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn


class EngagementNet(nn.Module):
    """MLP: (yaw, pitch, face_width_norm) -> P(engaged) in [0, 1]."""

    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(3, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.network(x)


class EngagementClassifier:
    """Loads trained weights and scores head-pose feature triples."""

    def __init__(self, model: EngagementNet):
        self._model = model
        self._model.eval()

    @classmethod
    def load(cls, weights_path: str | Path) -> "EngagementClassifier":
        if not Path(weights_path).exists():
            raise FileNotFoundError(
                f"Engagement model not found: {weights_path}. Train it with ml/train.py."
            )
        net = EngagementNet()
        net.load_state_dict(torch.load(weights_path, weights_only=True))
        return cls(net)

    def probability(self, yaw: float, pitch: float, distance: float) -> float:
        """Return P(engaged) for one feature triple."""
        with torch.no_grad():
            x = torch.tensor([[yaw, pitch, distance]], dtype=torch.float32)
            return float(self._model(x).item())
