"""Shorten the long pauses inside the narration over pictures.

A slide has one `in`/`out` pair into the narration, so a pause inside one
picture's words could never be cut by an edit of film.yaml: `init` cuts
the narration at its pauses only to decide where one picture ends and the
next begins. Measured on SUMIFS SUMPRODUCT vs DAX (2026-10-05): 30 pauses
of 0.6 s or more inside six pictures, 30.5 s of recording, every one of
them 4.6 dB or more under the speech line inside (docs/tech/audio.md).

So this writes a shorter COPY of the narration into analysis/tight/ --
the original in media/ is never touched -- and moves every number in
film.yaml that points into it: the pictures' `in`/`out`, and each
caption's `at`, `dur` and `words`. Nothing in the sound chain changes:
audio.py plays a shorter file exactly as it played the long one.

Camera takes are left alone on purpose. Their longest pause measured
0.90 s, and a cut there is a jump in the picture of a face.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import ingest
from .ffmpeg import ffmpeg_bin, ffprobe_bin
from .slides import _shot_blocks, quoted, tc

OVER = 0.6      # a pause this long or longer is shortened ...
KEEP = 0.4      # ... to this. Measured: 30 of the 50 pauses >= 0.25 s
                # on SUMIFS were >= 0.6 s; the 0.25-0.6 s ones are breaths.
FADE = 0.005    # each side of a join, so a cut never clicks. Inside
                # silence, and it shortens nothing.
TIGHT_DIR = "analysis/tight"


def cuts_for(quiet, windows, over: float = OVER, keep: float = KEEP):
    """The stretches of the recording to remove, in source seconds.

    Only a pause wholly inside one picture's words is cut: a pause that
    touches a picture's `in` or `out` is where `init` put the join, and
    one between pictures is never played anyway. The middle goes, and
    keep/2 is left either side so the words around it are untouched.
    """
    out = []
    for s, e in quiet:
        if e - s < over:
            continue
        if not any(a < s and e < b for a, b in windows):
            continue
        out.append((s + keep / 2, e - keep / 2))
    return sorted(out)


def moved(t: float, cuts) -> float:
    """Where moment `t` of the old recording is in the new one. A moment
    inside a cut lands where the cut was made."""
    gone = 0.0
    for a, b in cuts:
        if t >= b:
            gone += b - a
        elif t > a:
            gone += t - a
    return t - gone


def splice(samples: np.ndarray, rate: int, cuts) -> np.ndarray:
    """The recording with the cuts taken out. Exact length: no overlap
    at the joins, only a FADE-long fade either side of each, in silence.
    `samples` is (frames, channels)."""
    edges = [0]
    for a, b in cuts:
        edges += [int(round(a * rate)), int(round(b * rate))]
    edges.append(len(samples))
    n = max(1, int(FADE * rate))
    pieces = []
    for i in range(0, len(edges), 2):
        p = samples[edges[i]:edges[i + 1]].astype(np.float64)
        if i > 0 and len(p) > n:                       # after a cut
            p[:n] *= np.linspace(0.0, 1.0, n)[:, None]
        if i + 2 < len(edges) and len(p) > n:          # before a cut
            p[-n:] *= np.linspace(1.0, 0.0, n)[:, None]
        pieces.append(p)
    return np.concatenate(pieces).round().astype(samples.dtype)


def retime_text(text: str, film, voice: str, new_voice: str, cuts) -> str:
    """film.yaml AS TEXT with every shot on `voice` moved onto `new_voice`.

    `in`/`out` go through `moved`. A caption's times are film seconds,
    (source - in) / speed, so each is turned back into source seconds,
    moved, and divided again. Only those lines of those shots are
    rewritten; comments, notes and every other shot stay as they were.
    Captions not written one value per line raise ValueError, as in
    slides.refit_speed, rather than being guessed at.
    """
    lines = text.splitlines()
    shots = {s.id: s for s in film.shots}
    for sid, first, end, _dash in _shot_blocks(lines):
        shot = shots.get(sid)
        if shot is None or shot.voice != voice:
            continue
        sp = shot.speed
        tin = moved(shot.tin, cuts)
        src = lambda t: shot.tin + t * sp
        new = lambda t: (moved(src(t), cuts) - tin) / sp
        cap = -1
        seen = {"at": 0, "dur": 0, "words": 0}
        for i in range(first + 1, end):
            line = lines[i]
            m = re.match(r"^(\s+voice:\s*).*$", line)
            if m:
                lines[i] = m.group(1) + (new_voice if re.fullmatch(
                    r"[\w./-]+", new_voice) else quoted(new_voice))
                continue
            m = re.match(r'^(\s+)(in|out):\s*"?[0-9:.]+"?(\s*#.*)?$', line)
            if m and cap < 0:
                t = tin if m.group(2) == "in" else moved(shot.tout, cuts)
                lines[i] = f"{m.group(1)}{m.group(2)}: {tc(t)}{m.group(3) or ''}"
                continue
            if re.match(r"^\s+-\s+text:", line):
                cap += 1
                continue
            if cap < 0 or cap >= len(shot.captions):
                continue
            c = shot.captions[cap]
            m = re.match(r"^(\s+)(at|dur):\s*[0-9.]+\s*$", line)
            if m:
                key = m.group(2)
                seen[key] += 1
                v = new(c.at) if key == "at" else new(c.at + c.dur) - new(c.at)
                lines[i] = f"{m.group(1)}{key}: {v:.2f}"
                continue
            m = re.match(r"^(\s+words:\s*)\[.*\]\s*$", line)
            if m:
                seen["words"] += 1
                ws = [new(c.at + w) - new(c.at) for w in c.words]
                lines[i] = (m.group(1) + "["
                            + ", ".join(f"{w:.2f}" for w in ws) + "]")
        want = len(shot.captions)
        if (seen["at"], seen["dur"]) != (want, want) or \
                seen["words"] != sum(1 for c in shot.captions if c.words):
            raise ValueError(
                f"shot {sid}: its captions are not written one value per "
                f"line, so their times cannot be moved safely.")
    return "\n".join(lines) + "\n"


def find_cuts(path: Path, windows, over: float = OVER,
              keep: float = KEEP):
    """Measure the pauses in `path` (ingest's own detector: 50 ms RMS
    against a line between this recording's room and voice) and choose
    the cuts. Returns (cuts, the line in dB)."""
    pcm = ingest._pcm(path)
    if pcm is None:
        raise SystemExit(f"Could not read the sound of {path.name}.")
    quiet, line = ingest.quiet_stretches(ingest.window_levels(pcm), over)
    return cuts_for(quiet, windows, over, keep), line


def tight_name(voice: str, path: Path, cuts) -> str:
    """Where the shorter copy goes. Named by what it was made from and
    how, so it is never overwritten: an older film.yaml that `film undo`
    brings back still finds the file its numbers were written for."""
    key = hashlib.sha1(repr((path.name, path.stat().st_size,
                             [(round(a, 3), round(b, 3)) for a, b in cuts])
                            ).encode()).hexdigest()[:8]
    stem = re.sub(r"__tight_[0-9a-f]{8}$", "", Path(voice).stem)
    return f"{TIGHT_DIR}/{stem}__tight_{key}.wav"


def write_tight(src: Path, dst: Path, cuts) -> None:
    """Decode `src` at its own rate and channels, take the cuts out,
    write a 16-bit wav. The sound chain shapes it later like any voice."""
    r = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams",
                        "a:0", "-show_entries", "stream=sample_rate,channels",
                        "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True, check=True)
    rate, ch = (int(x) for x in r.stdout.strip().split(",")[:2])
    raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(src), "-vn",
                          "-ac", str(ch), "-ar", str(rate), "-f", "s16le",
                          "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw[:len(raw) // (2 * ch) * 2 * ch], dtype="<i2")
    y = splice(x.reshape(-1, ch), rate, cuts)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(y.astype("<i2").tobytes())
    tmp.replace(dst)
