"""
segment.py  --  where the person is, so the room behind them can blur.

Bokeh on a recorded take: the speaker sharp, the room soft. OpenCV runs
the model (`cv2.dnn`), so there is no new package -- but there is a model
FILE, fetched once into models/ and never committed. models/README.md
lists it with its URL and checksum.

Chosen by measuring two models on "I love you" (240 frames at 1:00):

    MediaPipe selfie, landscape   250 KB   10.8 ms/frame   blurred the room
    PP-HumanSeg (OpenCV zoo)      6.2 MB   18.3 ms/frame   kept the hanger
                                                           sharp: took it
                                                           for a person

The model sees a 256x144 thumbnail, so its mask is soft and a little
jumpy. Averaging each mask with the previous one halved the shimmer at
the edge (0.055 -> 0.029).
"""

from pathlib import Path

import cv2
import numpy as np

from . import models

# The file itself, its URL and its checksum are in models.CATALOGUE, which
# is what downloads it. These two names stay for the code that reads them.
MODEL_FILE = models.SELFIE.file
MODEL_URL = models.SELFIE.url
MODEL_SIZE = (256, 144)            # what the model looks at, width x height

# How soft the room is at `bokeh: 1`: the blur's sigma as a fraction of
# the frame width. The value the stills of 2026-09-14 were judged on.
BOKEH_BLUR = 0.048

# Weight of the new mask against the last one. 0.5 halved the shimmer;
# lower steadies more but lets the blur trail behind a moving head.
SMOOTH = 0.5


def models_dir() -> Path:
    return models.models_dir()


def missing_model(folder: Path | None = None) -> str | None:
    """None if the model is there, otherwise what to do about it."""
    folder = folder or models_dir()
    if (folder / MODEL_FILE).exists():
        return None
    return (f"`bokeh:` needs the model file {MODEL_FILE}, and it is not in\n"
            f"{folder}\n"
            f"It downloads on its own the first time bokeh is used, or now:\n"
            f"  uv run film models\n"
            f"By hand, 250 KB from\n  {MODEL_URL}\n"
            f"into that folder. It is never committed; see models/README.md.")


class Segmenter:
    """One frame in, a small person-probability mask out (1 = person)."""

    def __init__(self, folder: Path | None = None):
        path = models.ensure(models.SELFIE, folder)
        if path is None:
            raise SystemExit(missing_model(folder) or
                             f"{MODEL_FILE} could not be read.")
        self.net = cv2.dnn.readNetFromTFLite(str(path))

    def mask(self, bgr: np.ndarray) -> np.ndarray:
        small = cv2.resize(bgr, MODEL_SIZE, interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        self.net.setInput(cv2.dnn.blobFromImage(rgb))
        return np.squeeze(self.net.forward()).astype(np.float32)


class MaskSmoother:
    """Each mask averaged with the one before it, so the edge holds still."""

    def __init__(self):
        self.prev: np.ndarray | None = None

    def smooth(self, m: np.ndarray) -> np.ndarray:
        if self.prev is not None and self.prev.shape == m.shape:
            m = SMOOTH * m + (1.0 - SMOOTH) * self.prev
        self.prev = m
        return m


def bokeh(frame: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    """The frame sharp where the mask says person, blurred where it says room.

    The blur runs at quarter size and is enlarged back -- the same trick
    as render.blurred_fill, and at this softness it cannot be told apart.
    """
    if strength <= 0:
        return frame
    h, w = frame.shape[:2]
    sw, sh = max(8, w // 4), max(8, h // 4)
    small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0),
                             sigmaX=max(0.5, w * BOKEH_BLUR * strength / 4))
    back = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    m = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    m = np.clip(m, 0.0, 1.0)
    return cv2.blendLinear(frame, back, m, 1.0 - m)
