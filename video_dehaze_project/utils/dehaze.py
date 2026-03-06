# Shared dehazing helpers. Default path uses CLAHE, but we can transparently
# switch to neural backends (e.g., FFA-Net) whenever weights + torch are ready.

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import cv2
import numpy as np

try:
    import torch
    # Only import ffa_net if torch is available
    from models.ffa_net import load_pretrained
except ImportError:  # torch is optional until neural models are enabled
    torch = None  # type: ignore
    load_pretrained = None  # type: ignore

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_MODELS = {"auto", "clahe", "ffa_net"}
SUPPORTED_VIDEO_MODELS = {"auto", "clahe", "ffa_net"}


def simple_dehaze(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)


class DehazeEngine:
    """
    Runtime switch that picks between CLAHE and neural networks.

    Image/video defaults can be overridden via either environment variables or a
    `model_choice` form field on the `/dehaze` endpoint.
    """

    def __init__(self) -> None:
        self.image_default = os.environ.get("DEHAZE_IMAGE_MODEL", "clahe").lower()
        self.video_default = os.environ.get("DEHAZE_VIDEO_MODEL", "clahe").lower()
        self.ffa_weights = os.environ.get("DEHAZE_FFA_WEIGHTS", "").strip() or None
        try:
            self.ffa_blend = float(os.environ.get("DEHAZE_FFA_BLEND", "0.4"))
        except ValueError:
            self.ffa_blend = 0.4

        self._ffa_model = None
        self._ffa_device = None
        self._ffa_failed = False
        self._ffa_lock = threading.Lock()

    # ------------------------------------------------------------------ helpers
    def _resolve_choice(self, hint: Optional[str], default: str, allowed: set[str]) -> str:
        choice = (hint or "auto").lower()
        if choice not in allowed:
            logger.warning("Unsupported model '%s'; falling back to default", choice)
            choice = "auto"
        if choice == "auto":
            choice = default
        if choice not in allowed:
            logger.warning("Env default '%s' not supported; reverting to CLAHE", choice)
            return "clahe"
        return choice

    def _get_ffa_model(self):
        if self._ffa_model or self._ffa_failed:
            return self._ffa_model, self._ffa_device
        if torch is None or load_pretrained is None:
            logger.warning("PyTorch is not installed; cannot enable FFA-Net, using CLAHE.")
            self._ffa_failed = True
            return None, None
        with self._ffa_lock:
            if self._ffa_model or self._ffa_failed:
                return self._ffa_model, self._ffa_device
            try:
                model, device = load_pretrained(self.ffa_weights)
                self._ffa_model = model
                self._ffa_device = device
                logger.info("Loaded FFA-Net model (device=%s).", device)
            except Exception as exc:
                logger.warning("Failed to load FFA-Net: %s; falling back to CLAHE.", exc)
                self._ffa_failed = True
        return self._ffa_model, self._ffa_device

    @staticmethod
    def _to_tensor(frame: np.ndarray, device) -> torch.Tensor:
        tensor = torch.from_numpy(frame[:, :, ::-1].copy()).permute(2, 0, 1).float()
        tensor = tensor.unsqueeze(0) / 255.0
        return tensor.to(device)

    @staticmethod
    def _to_frame(tensor: torch.Tensor) -> np.ndarray:
        arr = tensor.squeeze(0).detach().cpu().clamp(0, 1).permute(1, 2, 0).numpy()
        arr = (arr * 255.0).astype(np.uint8)
        return arr[:, :, ::-1].copy()

    # ---------------------------------------------------------------- inference
    def process_image(self, frame: np.ndarray, model_hint: Optional[str] = None) -> np.ndarray:
        choice = self._resolve_choice(model_hint, self.image_default, SUPPORTED_IMAGE_MODELS)
        if choice == "clahe":
            return simple_dehaze(frame)
        model, device = self._get_ffa_model()
        if model is None or device is None:
            return simple_dehaze(frame)
        with torch.inference_mode():
            tensor = self._to_tensor(frame, device)
            output = model(tensor)
        ffa_frame = self._to_frame(output)
        alpha = min(max(self.ffa_blend, 0.0), 1.0)
        if alpha <= 0.0:
            return ffa_frame
        if alpha >= 1.0:
            return ffa_frame
        return cv2.addWeighted(frame, 1.0 - alpha, ffa_frame, alpha, 0.0)

    def process_video_frame(self, frame: np.ndarray, model_hint: Optional[str] = None) -> np.ndarray:
        choice = self._resolve_choice(model_hint, self.video_default, SUPPORTED_VIDEO_MODELS)
        if choice == "clahe":
            return simple_dehaze(frame)
        # Currently reuse the image model for per-frame enhancement
        model, device = self._get_ffa_model()
        if model is None or device is None:
            return simple_dehaze(frame)
        with torch.inference_mode():
            tensor = self._to_tensor(frame, device)
            output = model(tensor)
        ffa_frame = self._to_frame(output)
        alpha = min(max(self.ffa_blend, 0.0), 1.0)
        if alpha <= 0.0:
            return ffa_frame
        if alpha >= 1.0:
            return ffa_frame
        return cv2.addWeighted(frame, 1.0 - alpha, ffa_frame, alpha, 0.0)


engine = DehazeEngine()


def dehaze_image(frame: np.ndarray, model_hint: Optional[str] = None) -> np.ndarray:
    return engine.process_image(frame, model_hint=model_hint)


def dehaze_video_frame(frame: np.ndarray, model_hint: Optional[str] = None) -> np.ndarray:
    return engine.process_video_frame(frame, model_hint=model_hint)
