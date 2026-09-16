"""
models.py  --  the model files, fetched once, checked, kept in models/.

Two small files that are other people's and are never committed: one
finds you in the frame (bokeh), one takes the room out from under your
voice. They live in the toolkit's own `models/` folder, where you can
see them, and nowhere else -- not in a hidden cache in your user folder.

On a new computer nothing has to be done by hand. The first time a
model is needed it is downloaded, its SHA-256 is checked against the
number written here, and only then is it put in models/. `film models`
does the same for all of them at once, and `film doctor` says which
are there. Without a network the film still renders: the look or the
cleaning that needs the missing model is left out, and it says so.

Adding a model is one entry in CATALOGUE and one row in models/README.md;
a test keeps the two in agreement.

FFILM_MODELS moves the folder somewhere else.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .paths import toolkit_root


@dataclass(frozen=True)
class Model:
    file: str
    url: str
    size: int                # bytes
    sha256: str
    what: str                # what it is for, in the words `film models` prints


SELFIE = Model(
    file="selfie_segmenter_landscape.tflite",
    url=("https://storage.googleapis.com/mediapipe-models/image_segmenter/"
         "selfie_segmenter_landscape/float16/latest/"
         "selfie_segmenter_landscape.tflite"),
    size=250177,
    sha256="490e9ea734313e0de10fa0cd9e3c6133e36ea4db2b7a49bde9ef019f72796b8e",
    what="finds you in the frame, so the room behind you can blur (bokeh)",
)

# RNNoise, the "recording noise, speech signal" model of the rnnoise-models
# collection. Chosen over its "voice" sibling bd.rnnn by measurement on
# 2026-09-16 -- see docs/decisions/0008.
SPEECH_DENOISE = Model(
    file="sh.rnnn",
    url=("https://raw.githubusercontent.com/GregorR/rnnoise-models/master/"
         "somnolent-hogwash-2018-09-01/sh.rnnn"),
    size=297646,
    sha256="70bb6685eb0c2a1d18e2918dca3fbfbd39317010b1802eb1b6ea73a92f3fdec0",
    what="takes the room out from under your voice (RNNoise)",
)

CATALOGUE = (SELFIE, SPEECH_DENOISE)


def models_dir() -> Path:
    override = os.environ.get("FFILM_MODELS")
    return Path(override) if override else toolkit_root() / "models"


def path_of(model: Model, folder: Path | None = None) -> Path:
    return (folder or models_dir()) / model.file


def problem_with(data: bytes, model: Model) -> str | None:
    """Why these bytes are not this model, or None. Pure."""
    if len(data) != model.size:
        return (f"{model.file} came down as {len(data)} bytes, "
                f"expected {model.size}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != model.sha256:
        return f"{model.file} has the wrong checksum ({digest[:12]}...)"
    return None


def is_present(model: Model, folder: Path | None = None) -> bool:
    """There, and the right bytes. A half-downloaded file is not there."""
    p = path_of(model, folder)
    try:
        return problem_with(p.read_bytes(), model) is None
    except OSError:
        return False


def fetch(model: Model, folder: Path | None = None,
          opener=urllib.request.urlopen) -> Path:
    """Download, check, and only then put in place. A failed or wrong
    download leaves nothing behind -- a truncated model file is how a
    look quietly stops working."""
    dst = path_of(model, folder)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with opener(model.url, timeout=60) as r:
            data = r.read()
    except Exception as e:                           # network, DNS, HTTP
        raise SystemExit(f"Could not download {model.file}: {e}")
    wrong = problem_with(data, model)
    if wrong:
        raise SystemExit(f"Refused the download: {wrong}. Nothing was saved.")
    part = dst.with_name(dst.name + ".part")
    part.write_bytes(data)
    part.replace(dst)
    return dst


# Models that could not be had in this run. Every shot of a film asks
# again, and a minute of network timeout per shot would be worse than
# the missing model.
_given_up: set[str] = set()


def ensure(model: Model, folder: Path | None = None,
           say=print, opener=urllib.request.urlopen) -> Path | None:
    """The model's path, downloading it first if it is not there yet.
    None, with a line said, when it cannot be had."""
    if is_present(model, folder):
        return path_of(model, folder)
    if model.file in _given_up:
        return None                      # said once already, this run
    say(f"  fetching {model.file} ({model.size // 1000} KB, once) -- "
        f"{model.what}")
    try:
        return fetch(model, folder, opener)
    except SystemExit as e:
        say(f"  {e}")
        say(f"  Carrying on without it. `uv run film models` tries again.")
        _given_up.add(model.file)
        return None


def status_lines(folder: Path | None = None) -> list[str]:
    """One line per model, for `film doctor` and `film models`."""
    out = []
    for m in CATALOGUE:
        if is_present(m, folder):
            out.append(f"  ok    {m.file}  {m.what}")
        else:
            out.append(f"  --    {m.file} not downloaded yet: {m.what}. "
                       f"Happens on its own when needed, or `uv run film models`")
    return out
