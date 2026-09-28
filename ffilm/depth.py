"""
depth.py  --  how near each part of a photograph is, for parallax.

The camera over a photograph is a window sliding across a flat picture:
every pixel moves together. In a real camera move the near things slide
past the far ones. A depth map is enough to fake that -- render.py shifts
each pixel by how near it is (`depth:` in film.yaml, photographs only).

The model is Depth Anything V2 Small (Apache-2.0; Base and Large are
non-commercial). Photo in, depth out: 0 far .. 1 near.

It runs in onnxruntime, an OPTIONAL extra (`uv sync --extra depth`), not
in OpenCV's own cv2.dnn as bokeh does. Measured 2026-09-28, OpenCV 4.14:
cv2.dnn refused all three onnx-community files ("dynamic 'zero' shapes
are not supported") and fabio-sim's fixed-size export too (a custom
layer it cannot build). Without onnxruntime the film renders flat and
says so once. docs/decisions/0013 has the numbers.

Made once per photo and kept in analysis/depth/, like a proxy: 1.3-2.2 s
a photo on this PC, and never again unless the photo changes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from . import models, pix

SHORT_SIDE = 518                 # what the model was trained to look at
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

# How soft the depth map is, as a fraction of its width. A sharp map tears
# the picture where near meets far; a soft one stretches it instead.
DEPTH_BLUR = 0.012


def missing_runner() -> str | None:
    """None if onnxruntime is installed, otherwise what to do about it."""
    try:
        import onnxruntime  # noqa: F401
        return None
    except ImportError:
        return ("`depth:` needs onnxruntime, which is an optional extra:\n"
                "  uv sync --extra depth\n"
                "Until then the photographs render flat, as before.")


def model_blob(bgr: np.ndarray) -> np.ndarray:
    """The photo as the model wants it: RGB, short side 518, both sides a
    multiple of 14, ImageNet-normalised, NCHW. Pure."""
    h, w = bgr.shape[:2]
    s = SHORT_SIDE / min(h, w)
    nh = max(14, int(round(h * s / 14)) * 14)
    nw = max(14, int(round(w * s / 14)) * 14)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_CUBIC)
    x = (rgb.astype(np.float32) / 255.0 - MEAN) / STD
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])


def normalise(raw: np.ndarray) -> np.ndarray:
    """The model's output -> 0 far .. 1 near, softened. Pure.

    The model gives relative inverse depth: bigger is nearer, in no unit.
    Stretched to 0..1 per photo, because only the order matters here."""
    d = np.squeeze(raw).astype(np.float32)
    lo, hi = float(d.min()), float(d.max())
    d = (d - lo) / (hi - lo) if hi - lo > 1e-6 else np.zeros_like(d)
    sigma = max(0.5, d.shape[1] * DEPTH_BLUR)
    return np.clip(cv2.GaussianBlur(d, (0, 0), sigma), 0.0, 1.0)


def cache_name(key: str, photo: Path) -> str:
    """analysis/depth/<key>__<8 hex>.png. The hex is the photo's size and
    time, so a photo replaced under the same name gets a new map."""
    st = photo.stat()
    tag = hashlib.sha1(f"{st.st_size}:{st.st_mtime_ns}".encode()).hexdigest()[:8]
    return f"{key}__{tag}.png"


class DepthModel:
    """One photo in, its depth map out (float32, 0 far .. 1 near)."""

    def __init__(self, folder: Path | None = None):
        msg = missing_runner()
        if msg:
            raise SystemExit(msg)
        path = models.ensure(models.DEPTH, folder)
        if path is None:
            raise SystemExit(f"{models.DEPTH.file} could not be had.")
        import onnxruntime as ort
        self.sess = ort.InferenceSession(str(path),
                                         providers=["CPUExecutionProvider"])
        self.input = self.sess.get_inputs()[0].name

    def depth(self, bgr: np.ndarray) -> np.ndarray:
        raw = self.sess.run(None, {self.input: model_blob(bgr)})[0]
        return normalise(raw)


_model: DepthModel | None = None


def depth_for(photo: Path, cached: Path) -> np.ndarray:
    """The photo's depth map, read from `cached` if it is there, made and
    kept there if not. At the model's resolution; the caller resizes.

    Kept as 16-bit PNG: 8 bits would step the depth into 256 terraces,
    and a terrace edge is a line the parallax draws across the picture."""
    global _model
    got = pix.imread(cached, cv2.IMREAD_UNCHANGED) if cached.exists() else None
    if got is not None and got.dtype == np.uint16:
        return got.astype(np.float32) / 65535.0
    img = pix.imread(photo, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Could not read image: {photo}")
    if _model is None:
        _model = DepthModel()
    d = _model.depth(img)
    cached.parent.mkdir(parents=True, exist_ok=True)
    pix.imwrite(cached, np.round(d * 65535.0).astype(np.uint16))
    return d
