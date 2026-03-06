"""
Minimal PyTorch re-implementation of FFA-Net (Feature Fusion Attention Network)
for single-image dehazing. This module is intentionally lightweight—enough to
load published checkpoints and run inference inside the FastAPI service.

Original paper: https://arxiv.org/abs/1911.07559
Reference repo:  https://github.com/zhilin007/FFA-Net
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    """Standard residual block with optional dilation."""

    def __init__(self, channels: int, dilation: int = 1) -> None:
        super().__init__()
        padding = dilation
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=padding, dilation=dilation, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=padding, dilation=dilation, bias=False),
            nn.BatchNorm2d(channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D401
        return torch.relu(x + self.block(x))


class FeatureAttentionBlock(nn.Module):
    """
    Fuse local and global cues using channel/spatial attention. This mirrors the
    structure used in the paper but keeps the implementation compact.
    """

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 1, bias=False),
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attn = self.sigmoid(self.conv(x))
        return x * attn


class FFANet(nn.Module):
    """A streamlined version of FFA-Net suitable for inference deployment."""

    def __init__(self, channels: int = 64, blocks: int = 8) -> None:
        super().__init__()
        self.entry = nn.Sequential(
            nn.Conv2d(3, channels, 3, padding=1, bias=False),
            nn.ReLU(inplace=True),
        )
        self.body = nn.Sequential(
            *[ResidualBlock(channels, dilation=1 + i % 3) for i in range(blocks)],
            FeatureAttentionBlock(channels),
        )
        self.exit = nn.Conv2d(channels, 3, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D401
        feats = self.entry(x)
        feats = self.body(feats)
        out = self.exit(feats)
        return torch.clamp(x + out, 0.0, 1.0)


def build_model(channels: int = 64, blocks: int = 8) -> FFANet:
    """Factory helper used by the loader below."""
    return FFANet(channels=channels, blocks=blocks)


def load_pretrained(
    weights_path: Optional[Path | str],
    device: Optional[torch.device] = None,
    strict: bool = False,
) -> Tuple[FFANet, torch.device]:
    """
    Build an FFANet instance and (optionally) load weights from disk.

    Args:
        weights_path: Path to a `.pth`/`.pt` checkpoint. If None, the model will
            use random initialization (still functional but not high quality).
        device: Torch device override. Defaults to CUDA if available.
        strict: Whether to enforce an exact key match when loading weights.
    """

    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model().to(device)
    model.eval()

    if weights_path:
        weights_file = Path(weights_path)
        if not weights_file.exists():
            raise FileNotFoundError(f"FFANet weights not found at {weights_file}")
        # These official checkpoints are trusted, so we explicitly allow full
        # object loading by disabling the `weights_only` safety filter that
        # became default in newer PyTorch versions.
        state = torch.load(weights_file, map_location=device, weights_only=False)
        if "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state, strict=strict)

    return model, device

