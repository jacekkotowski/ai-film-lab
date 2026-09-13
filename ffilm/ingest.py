"""
ingest.py  --  look at the raw material and write down what is there.

Produces, in <project>/analysis/:
    manifest.json     every file, its size/duration, and a suggested focus point
    thumbs/           one thumbnail per still, several per video
    contact.jpg       everything on one sheet, numbered
    proxies/          480p copies of every video, for fast previewing
    cuts/<name>.json  detected shot boundaries inside each video

The contact sheet is the important output. It is what I look at when you
ask me to build a sequence -- it is how the toolkit and I share an eye.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import kinds
from . import pix
from .ffmpeg import ffmpeg_bin, ffprobe_bin
from .spec import Shot

STILL_EXT = kinds.STILL

# What an iPhone shoots by default. Neither OpenCV nor Pillow can open it,
# so before this existed every iPhone photo dropped into media/ vanished in
# silence -- no error, no mention, just missing from the film.
HEIC_EXT = kinds.HEIC

# Where an unreadable video gets moved, so it neither breaks a future
# ingest nor sits there forever looking like it is still waiting to be
# used. Inside media/, not deleted: "originals are read-only" means kept,
# not judged -- a file ffprobe gave up on may still be worth a second
# look or a repair tool, and that call is always yours, not this
# toolkit's. Named in kinds.py because guide.py scans media/ too.
UNREADABLE_DIRNAME = kinds.UNREADABLE_DIRNAME


# --------------------------------------------------------------------------
# Naming the derived files
# --------------------------------------------------------------------------


def analysis_keys(rels: list[str]) -> dict[str, str]:
    """A name for each media file's derived artefacts -- its proxy, its
    cuts, its thumbnails, its extracted audio, its converted jpg.

    All five used to be `<stem>.<ext>`, and media/ is scanned
    recursively, so any two files sharing a stem shared all five:

        media/dzien1/IMG_0042.MOV   and   media/dzien2/IMG_0042.mp4
        IMG_0042.HEIC               and   IMG_0042.JPG

    Both of those come off an ordinary phone or camera card, where
    numbering restarts and the same counter appears in every folder. The
    second file overwrote the first's proxy, and the film then showed
    one clip where two were meant.

    So the key is the stem where the stem is unique, and the stem plus a
    little of the path's hash where it is not. Unique is the ordinary
    case -- one flat media/ folder of differently-named files -- which
    means every project that already exists keeps the exact names it has
    and nothing is re-analysed for the sake of this.
    """
    seen: dict[str, int] = {}
    for rel in rels:
        stem = Path(rel).stem
        seen[stem] = seen.get(stem, 0) + 1

    keys: dict[str, str] = {}
    for rel in rels:
        stem = Path(rel).stem
        if seen[stem] == 1:
            keys[rel] = stem
        else:
            tag = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:6]
            keys[rel] = f"{stem}_{tag}"
    return keys


def key_of(project: Path, src: str) -> str:
    """The key ingest gave this file, read back off the manifest.

    Falls back to the bare stem, which is what a manifest written before
    keys existed implies -- so an old project keeps working with no
    re-ingest.
    """
    mf = project / "analysis" / "manifest.json"
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Path(src).stem
    want = Path(src).as_posix()
    for e in data.get("media", []):
        if e.get("path") == want:
            return e.get("key") or Path(src).stem
    return Path(src).stem


def sound_of(project: Path, src: str) -> dict | None:
    """What ingest measured about the sound on this file, or None.

    None for anything ingest never looked at -- a narration track kept
    outside media/, a manifest written before these numbers existed, a
    project whose analysis/ has been deleted. Every caller has to have an
    answer for that, because "no analysis yet" is an ordinary state of
    this tool and not an error.
    """
    mf = project / "analysis" / "manifest.json"
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    want = Path(src).as_posix()
    for e in data.get("media", []):
        if e.get("path") == want:
            sound = e.get("sound")
            return sound if isinstance(sound, dict) and sound.get("has") else None
    return None


# --------------------------------------------------------------------------
# Where is the thing that matters?
# --------------------------------------------------------------------------


def faces_available() -> bool:
    """Whether this OpenCV can detect faces at all.

    OpenCV 5 removed CascadeClassifier and ships no cascade XML files, so
    on a current install the face branch of `find_focus` cannot run. It
    used to be wrapped in a bare `except: pass`, which meant every
    picture quietly fell through to detail energy and the toolkit went on
    claiming "faces first" -- including the rule that gives shots with
    faces a longer duration, which had therefore never once fired.

    Better to know. `film doctor` says so out loud.
    """
    return hasattr(cv2, "CascadeClassifier") and bool(
        _cascade_file())


def _cascade_file() -> str:
    import os
    try:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    except AttributeError:
        return ""
    return path if os.path.exists(path) else ""


def speaker_focus(path: Path, samples: int = 32) -> tuple[float, float] | None:
    """Where the person is in a talking clip, without a face detector.

    A talking head is the only thing in a webcam frame that MOVES: the
    wall behind does not, the lamp does not. Accumulating frame-to-frame
    difference across the clip therefore lights up exactly the speaker,
    and the centroid of that is where to point the camera. No model, no
    download, nothing to keep up to date -- and it keeps working when
    somebody looks away or covers their face, which is where a face
    detector gives up.

    Returns None when nothing moved enough to be worth trusting, and the
    caller falls back to the middle.
    """
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total < 2:
        cap.release()
        return None

    prev, acc = None, None
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * i / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        grey = cv2.cvtColor(cv2.resize(frame, (320, 180)),
                            cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            diff = np.abs(grey - prev)
            acc = diff if acc is None else acc + diff
        prev = grey
    cap.release()
    if acc is None or acc.max() < 1e-3:
        return None

    acc = cv2.GaussianBlur(acc, (0, 0), 6)
    if acc.sum() <= 0:
        return None

    # The whole map, with no threshold. Measured, and it was the opposite
    # of the guess: trimming to the busiest part pulls the answer onto
    # the mouth and nose -- the fastest-moving patch of a face, but sat
    # well to one side of it whenever the head is turned. On a 77 second
    # take the untrimmed centroid landed on 0.484 against a face centred
    # at 0.48; a 70th-percentile floor moved it to 0.407, which is an ear
    # out of frame.
    cols, rows = acc.sum(axis=0), acc.sum(axis=1)
    x = float((cols * np.arange(cols.size)).sum() / cols.sum()) / cols.size
    y = float((rows * np.arange(rows.size)).sum() / rows.sum()) / rows.size
    # Lift the point towards the eyes. The motion centroid sits on the
    # mouth and jaw, because that is what moves most; framing on it puts
    # the head high and cuts the crown off.
    y = max(0.0, y - 0.10)
    return (round(min(1.0, max(0.0, x)), 3), round(y, 3))


def find_focus(img: np.ndarray) -> tuple[tuple[float, float], str]:
    """Return a normalised (x, y) point of interest, and how we found it.

    Faces first, because a face is almost always the subject. Otherwise
    fall back to detail energy: the part of the frame with the most
    structure is usually the part worth looking at.
    """
    h, w = img.shape[:2]
    small = cv2.resize(img, (min(900, w), int(min(900, w) * h / w)))
    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    try:
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(grey, 1.15, 6, minSize=(28, 28))
        if len(faces):
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            sh, sw = grey.shape
            return ((fx + fw / 2) / sw, (fy + fh / 3) / sh), "face"
    except Exception:
        pass

    # Detail energy: where is the structure?
    lap = np.abs(cv2.Laplacian(grey, cv2.CV_32F, ksize=3))
    lap = cv2.GaussianBlur(lap, (0, 0), sigmaX=max(grey.shape) / 28.0)
    thresh = np.percentile(lap, 88)
    mask = (lap >= thresh).astype(np.float32)
    if mask.sum() < 10:
        return (0.5, 0.5), "centre"
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    cx = float((xx * mask).sum() / mask.sum() / mask.shape[1])
    cy = float((yy * mask).sum() / mask.sum() / mask.shape[0])
    # Pull it back towards centre a little -- pure centroids can be extreme.
    return (0.5 + (cx - 0.5) * 0.8, 0.5 + (cy - 0.5) * 0.8), "detail"


# --------------------------------------------------------------------------
# ffprobe / ffmpeg helpers
# --------------------------------------------------------------------------


# Nothing here may hang the whole ingest. ffmpeg on a truncated or
# malformed file can sit forever without printing anything, and a
# toolkit that stops responding with no message is worse than one that
# says "I could not read that". Generous, because a long clip really
# does take a while to walk: this is a stuck-process limit, not a
# performance one.
PROBE_TIMEOUT = 60          # reading metadata: seconds, or it is stuck
PASS_TIMEOUT = 1800         # a whole pass over the audio or the picture


def _run(args: list[str], timeout: int):
    """subprocess.run, but a hung or missing ffmpeg is not a traceback.

    Returns None when it could not be run or did not finish, which every
    caller already has to handle for the non-zero-exit case anyway.
    """
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def probe(path: Path) -> dict:
    exe = ffprobe_bin()
    out = _run([exe, "-v", "error", "-print_format", "json", "-show_format",
                "-show_streams", str(path)], PROBE_TIMEOUT)
    if out is None or out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout or "{}")
    except ValueError:
        return {}


def video_info(path: Path) -> dict:
    d = probe(path)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    fps = 25.0
    if v.get("r_frame_rate", "0/0") != "0/0":
        try:
            a, b = v["r_frame_rate"].split("/")
            fps = float(a) / float(b)
        except Exception:
            pass
    return {
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": round(fps, 3),
        "duration": picture_duration(d, v, fps),
    }


def picture_duration(probed: dict, video: dict, fps: float) -> float:
    """How long there are PICTURES for -- not how long the file is.

    These are not the same number, and the difference is what put five
    lines of OpenCV error at the end of a render. A webcam recording
    stops when it stops: the container is stamped with the longest of
    its streams, so a file whose picture ends at 49.83s reports 50.10,
    the edit is written up to 50.10, and the last eight frames asked for
    do not exist.

    So: the video stream's own duration, then the frame count over the
    rate, and only then the container -- which is the answer that is
    always present and sometimes wrong.
    """
    def num(x) -> float:
        try:
            v = float(x)
            return v if v > 0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    frames = num(video.get("nb_frames"))
    return round(
        num(video.get("duration"))
        or (frames / fps if frames and fps else 0.0)
        or num(probed.get("format", {}).get("duration")), 2)


def convert_heic(src: Path, dst: Path) -> bool:
    """iPhone photo -> an ordinary jpg the rest of the toolkit can read.

    Written into analysis/, never into media/. Originals stay untouched,
    which is the one rule about media/ that never bends.
    """
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = _run(
        # -map 0:v:0 on purpose: a HEIC can carry more than one image
        # (thumbnails, depth maps, HDR gain maps). Take the first, which is
        # the photo, not whatever ffmpeg decides is "best".
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(src), "-map", "0:v:0", "-frames:v", "1", "-q:v", "2",
         str(dst)],
        PROBE_TIMEOUT)
    return r is not None and r.returncode == 0 and dst.exists()


# A proxy is a 480p stand-in for `peek` and `draft`, which are the rough
# looks by definition. Sixty of them a second is more than either can
# use -- the film itself renders at 24 -- and they cost time and disk to
# make. Measured on a 109s 1080p60 take: 17.7s and 7.0MB at the source's
# own rate, 14.9s and 5.6MB at 30. Faster AND smaller, which is not a
# trade at all.
PROXY_FPS = 30


def make_proxy(src: Path, dst: Path, height: int = 480) -> bool:
    """The 480p stand-in. Software decoding on purpose.

    -hwaccel looks like the obvious win here and is the opposite of one:
    the GPU decodes, and then every frame has to be copied back to system
    memory for `scale`, which costs more than the decode saved. Measured
    on this machine against 17.2s of plain software: dxva2 25.4s, qsv
    29.3s, d3d11va 41.3s, and nvenc wrote nothing at all. Paying for it
    properly would mean the whole filter chain on the GPU, which is a
    different toolkit.
    """
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Not check=True. One file ffmpeg dislikes used to raise
    # CalledProcessError out of the middle of the loop and take the whole
    # ingest with it -- so forty good photographs were lost to one bad
    # clip. The caller sets that file aside instead.
    r = _run(
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
         "-vf", f"fps={PROXY_FPS},scale=-2:{height}",
         "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "28", "-g", "12", "-an", str(dst)], PASS_TIMEOUT)
    return r is not None and r.returncode == 0 and dst.exists()


def quarantine(path: Path, media: Path, where: str | None = None) -> Path:
    """Move a file out of the way, into a named folder inside media/.

    Two callers: ingest, for a video it could not read, and `film
    record`, for a take you fluffed and asked to do again. Moved, never
    deleted, in both cases -- see UNREADABLE_DIRNAME. Numbered instead
    of overwritten on a name clash, for the same reason record.py never
    reuses a take's filename: two files landing on one name would mean
    losing whichever one lost the collision.
    """
    folder = media / (where or UNREADABLE_DIRNAME)
    folder.mkdir(exist_ok=True)
    dst = folder / path.name
    n = 2
    while dst.exists():
        dst = folder / f"{path.stem}_{n}{path.suffix}"
        n += 1
    path.rename(dst)
    return dst


def loudness(path: Path) -> tuple[float, float] | None:
    """(mean, peak) level of the clip in dBFS, or None if it has no audio."""
    r = _run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-vn",
              "-af", "volumedetect", "-f", "null", "-"], PASS_TIMEOUT)
    if r is None or r.returncode != 0:
        return None
    mean = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", r.stderr)
    peak = re.search(r"max_volume:\s*(-?[0-9.]+) dB", r.stderr)
    if not mean or not peak:
        return None
    return float(mean.group(1)), float(peak.group(1))


def silence_floor(path: Path) -> float:
    """How quiet is "silence" ON THIS CLIP, in dB.

    A fixed -32dB was the first attempt and it was wrong: it is a level,
    not a judgement, and a sentence spoken softly sits below it. Whole
    quiet phrases were being cut as though they were pauses.

    So measure the clip and work down from its own average. Speech varies
    by maybe 10-15dB around its mean; room tone sits far below. A generous
    margin under the mean lands between the two, and the clamp stops a very
    loud or very quiet recording from producing a silly threshold.

    Kept for `--floor` and for anything that still wants one number. The
    pause finder no longer uses it -- see quiet_stretches for why a single
    threshold could not do this job.
    """
    lv = loudness(path)
    if lv is None:
        return -32.0
    mean, _peak = lv
    return max(-60.0, min(-30.0, mean - 18.0))


# How long a slice of audio to judge at a time. Short enough to land a cut
# on a real beat, long enough that one loud sample is not a whole verdict.
LEVEL_WINDOW = 0.05

# The analysis rate. Speech lives well under 8kHz and this is only ever
# measuring loudness, so 16k is plenty -- and it is the same rate voice.py
# already extracts at.
LEVEL_RATE = 16000

# Where the line between "room" and "talking" goes, as a fraction of the
# way from one to the other, in dB. Measured on a real take: room at -47,
# speech at -16, so this puts it at -36 -- comfortably above the room and
# 20dB under the voice.
QUIET_FRACTION = 0.35

# Under this much difference between the quietest and the loudest of a
# take, there is nothing to tell apart: a clip of constant traffic, or one
# recorded so hot that the room and the voice are the same size. Keep it
# whole rather than guess. Same principle as MAX_TRIM in scaffold.
NEEDS_RANGE_DB = 12.0


def _pcm(path: Path, rate: int = LEVEL_RATE):
    """The audio as mono samples, or None. One decode, no temp file.

    Its own subprocess call and not `_run`, which asks for text: samples
    are bytes, and decoding them as UTF-8 would not merely mangle a
    message, it would change the numbers.
    """
    try:
        r = subprocess.run(
            [ffmpeg_bin(), "-v", "error", "-i", str(path), "-vn",
             "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
            capture_output=True, timeout=PASS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or len(r.stdout) < 2:
        return None
    raw = r.stdout
    return np.frombuffer(raw[:len(raw) // 2 * 2], dtype="<i2")


def window_levels(pcm, rate: int = LEVEL_RATE,
                  window: float = LEVEL_WINDOW) -> np.ndarray:
    """How loud each slice of the take is, in dBFS. Pure, so the rule it
    feeds can be tested on made-up audio instead of on a recording."""
    n = max(1, int(rate * window))
    m = len(pcm) // n
    if m < 1:
        return np.zeros(0)
    block = np.asarray(pcm[:m * n], dtype=np.float64).reshape(m, n)
    rms = np.sqrt((block ** 2).mean(axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-9) / 32768.0)


def quiet_stretches(levels: np.ndarray, min_gap: float,
                    window: float = LEVEL_WINDOW
                    ) -> tuple[list[tuple[float, float]], float]:
    """The pauses in a take, and the level they were judged against.

    Why this is not ffmpeg's silencedetect any more, measured on a real
    310-second take that came back with NO pauses at all and was left
    whole -- 310 seconds of one shot, room tone and all:

        the room, per 50ms window     -46 dBFS RMS   but  -33 dBFS PEAK
        the voice                     -20 dBFS RMS   and  -10 dBFS PEAK
        threshold silence_floor gave  -39 dBFS

    silencedetect compares PEAK samples: every sample must sit under the
    threshold for the whole gap. The room's peaks are -33, the threshold
    was -39, so not one moment of that take ever counted as quiet. The
    threshold was not wrong by a little -- it was measured on RMS and
    applied to peaks, which are a different quantity, about 10dB apart.

    Judging the same take on RMS finds 34 pauses of a second and a half or
    more, 119 seconds of them, the longest 11.4 seconds.

    So: measure each window's RMS, find where the room is and where the
    voice is in that take's own distribution, and put the line between
    them. Nothing here is a fixed level, because a level cannot survive
    one person's quiet flat and another person's noisy kitchen.
    """
    if levels.size == 0:
        return [], -32.0
    floor = float(np.percentile(levels, 10))
    voice = float(np.percentile(levels, 90))
    if voice - floor < NEEDS_RANGE_DB:
        # Nothing to tell apart. Keep the take whole.
        return [], floor
    line = floor + (voice - floor) * QUIET_FRACTION

    quiet: list[tuple[float, float]] = []
    below = levels < line
    start = None
    for i, b in enumerate(below):
        if b and start is None:
            start = i
        elif not b and start is not None:
            if (i - start) * window >= min_gap:
                quiet.append((start * window, i * window))
            start = None
    if start is not None and (len(below) - start) * window >= min_gap:
        quiet.append((start * window, len(below) * window))
    return quiet, line


def detect_sound(path: Path, duration: float, floor: str | None = None,
                 min_gap: float = 0.6) -> dict:
    """Where is there sound on this clip, and where are the pauses in it?

    One ffmpeg pass over the audio only. This is deliberately NOT speech
    recognition -- we only want two facts. Was anyone recording sound at
    all (if you talked over a clip, the words are the point of it, and
    sampling four seconds out of the middle throws them away). And where
    are the natural gaps, so a long take can be cut at a breath instead
    of mid-word.

    Runs on the ORIGINAL, not the proxy -- proxies are built with -an.
    """
    quiet_none = {"has": False, "ratio": 0.0, "in": 0.0, "out": duration,
                  "quiet": []}
    if duration <= 0:
        return quiet_none

    pcm = _pcm(path)
    if pcm is None or pcm.size == 0:
        return quiet_none                       # no audio stream at all

    levels = window_levels(pcm)
    # Where the room is and where the voice is, on THIS take. Two numbers
    # that quiet_stretches works out anyway and used to throw away after
    # putting one line between them -- and they are the only honest basis
    # for any threshold applied to this take later. audio.py reads them
    # back off the manifest rather than measuring the same file again;
    # see ffilm/audio.py, tuning_for.
    room_db = float(np.percentile(levels, 10)) if levels.size else -60.0
    voice_db = float(np.percentile(levels, 90)) if levels.size else -20.0
    if floor is None:
        found, db = quiet_stretches(levels, min_gap)
    else:
        # An explicit level, from `--floor`. Honour it exactly.
        db = float(str(floor).rstrip("dB"))
        found, _ = quiet_stretches(
            np.where(levels < db, -120.0, 0.0), min_gap)

    quiet = [(max(0.0, s), min(duration, e)) for s, e in found]
    ratio = max(0.0, 1.0 - sum(e - s for s, e in quiet) / duration)
    if ratio < 0.02:
        return quiet_none

    # Where the sound actually begins and ends, ignoring lead-in and tail.
    first = quiet[0][1] if quiet and quiet[0][0] <= 0.15 else 0.0
    last = quiet[-1][0] if quiet and quiet[-1][1] >= duration - 0.15 else duration
    inner = [[round(s, 2), round(e, 2)] for s, e in quiet if first < s and e < last]

    return {"has": True, "ratio": round(ratio, 3), "in": round(first, 2),
            "out": round(last, 2), "quiet": inner, "floor_db": round(db, 1),
            "room_db": round(room_db, 1), "voice_db": round(voice_db, 1)}


def detect_cuts(path: Path, threshold: float = 0.28) -> list[float]:
    """Shot boundaries, in seconds. Run this on the proxy -- much faster."""
    r = _run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-filter:v",
              f"select='gt(scene,{threshold})',showinfo",
              "-f", "null", "-"], PASS_TIMEOUT)
    if r is None:
        return []
    return sorted({round(float(m), 2)
                   for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)})


# --------------------------------------------------------------------------
# Thumbnails and the contact sheet
# --------------------------------------------------------------------------


def thumb_of(img: np.ndarray, width: int = 420) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.resize(img, (width, max(1, int(width * h / w))),
                      interpolation=cv2.INTER_AREA)


def contact_sheet(entries: list[dict], thumbs_dir: Path, out: Path,
                  cols: int = 5, cell: int = 380) -> None:
    """One numbered grid of everything. Numbers match manifest.json."""
    tiles = []
    for e in entries:
        tp = thumbs_dir / e["thumb"]
        img = pix.imread(tp)
        if img is None:
            continue
        h, w = img.shape[:2]
        s = min(cell / w, (cell * 9 / 16) / h)
        img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))),
                         interpolation=cv2.INTER_AREA)
        pad = np.full((int(cell * 9 / 16) + 34, cell, 3), 24, np.uint8)
        y0 = (int(cell * 9 / 16) - img.shape[0]) // 2
        x0 = (cell - img.shape[1]) // 2
        pad[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img

        # Mark the detected focus point so you can see if it is sensible.
        if e.get("focus"):
            fx = int(x0 + e["focus"][0] * img.shape[1])
            fy = int(y0 + e["focus"][1] * img.shape[0])
            cv2.drawMarker(pad, (fx, fy), (60, 220, 255), cv2.MARKER_CROSS, 18, 2)

        label = f'{e["n"]:02d} {Path(e["path"]).name[:30]}'
        if e["kind"] == "video":
            label += f'  {e.get("duration", 0):.0f}s'
        cv2.putText(pad, label, (8, pad.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (235, 235, 235), 1, cv2.LINE_AA)
        tiles.append(pad)

    if not tiles:
        return
    rows = []
    for i in range(0, len(tiles), cols):
        row = tiles[i:i + cols]
        while len(row) < cols:
            row.append(np.full_like(tiles[0], 24))
        rows.append(np.hstack(row))
    pix.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])


# --------------------------------------------------------------------------
# What order were these taken in?
# --------------------------------------------------------------------------

# EXIF tag 36867, DateTimeOriginal: when the shutter actually fired.
_EXIF_TAKEN = 36867
_EXIF_FORMAT = "%Y:%m:%d %H:%M:%S"


def taken_at(path: Path, probed: dict | None = None) -> float | None:
    """When this was photographed or filmed. None when nothing says.

    NOT the file's modification time. A folder copied off a card has
    every mtime within the same second, in whatever order the copy
    happened to run -- which is no order at all, and worse than none,
    because it looks like one.
    """
    from datetime import datetime

    suffix = path.suffix.lower()
    if suffix in STILL_EXT:
        try:
            from PIL import Image
            with Image.open(path) as im:
                exif = im.getexif()
            when = exif.get(_EXIF_TAKEN) if exif else None
            if when:
                return datetime.strptime(str(when),
                                         _EXIF_FORMAT).timestamp()
        except Exception:
            return None
        return None

    tags = (probed or {}).get("format", {}).get("tags", {}) or {}
    when = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
    if not when:
        return None
    try:
        return datetime.fromisoformat(
            str(when).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def in_capture_order(files: list[Path], when: dict[Path, float | None]
                     ) -> list[Path]:
    """Chronological if every file says when it was taken; otherwise the
    alphabetical order it already had.

    All-or-nothing on purpose. A part-timed set sorted by time puts the
    photographs in order and then dumps the screen recording that has no
    timestamp somewhere arbitrary -- which is a worse answer than the
    filenames, and a much harder one to argue with. Numbered filenames
    (00_, 01_) still win over both: `scaffold` re-sorts on those after.
    """
    if not files or any(when.get(p) is None for p in files):
        return files
    return sorted(files, key=lambda p: (when[p], p.as_posix()))


# --------------------------------------------------------------------------
# The main entry point
# --------------------------------------------------------------------------


# Bumped whenever what ingest WORKS OUT about a file changes, as opposed
# to the file itself. The cache keys on the file, so without this a
# improvement to the analysis would never reach anything already
# analysed: the pause finder was rewritten and every take on the disk
# would have gone on using the answer the old one got.
#
# 1  the original
# 2  pauses found on windowed RMS instead of ffmpeg's peak-based
#    silencedetect -- see quiet_stretches
ANALYSIS_VERSION = 2


def _fingerprint(path: Path) -> list:
    """Enough to say "this is the same file it was last time"."""
    try:
        st = path.stat()
    except OSError:
        return [0, 0.0]
    return [st.st_size, round(st.st_mtime, 3)]


def _previous(analysis: Path) -> dict[str, dict]:
    """Last run's manifest, keyed by path, for reuse."""
    try:
        data = json.loads(
            (analysis / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {e["path"]: e for e in data.get("media", []) if e.get("path")}


def _top_up_sound(entry: dict, path: Path) -> dict:
    """Add a fact learned since this entry was written, without redoing
    the entry.

    Bumping ANALYSIS_VERSION is the blunt way to say "we know more than
    we did then", and for a new fact about the SOUND it is far too blunt:
    it would re-encode every proxy and re-cut every clip in every project
    to learn two numbers that one pass over the audio already gives. So
    the version stays where it is and the missing fact is filled in.

    Only ever adds. An entry that already has the numbers is returned
    untouched, and so is one with no sound to measure.
    """
    sound = entry.get("sound")
    if not isinstance(sound, dict) or not sound.get("has"):
        return entry
    if sound.get("room_db") is not None:
        return entry
    fresh = detect_sound(path, float(entry.get("duration") or 0.0))
    if not fresh.get("has"):
        return entry
    entry = dict(entry)
    entry["sound"] = {**sound,
                      "room_db": fresh.get("room_db"),
                      "voice_db": fresh.get("voice_db")}
    return entry


def _still_usable(entry: dict, project: Path, path: Path) -> bool:
    """May last run's answer for this file stand?

    Only when the file is byte-for-byte where it was, and everything the
    entry points at is still on disk. Deleting analysis/ has always been
    safe and has to stay safe.
    """
    if entry.get("analysis") != ANALYSIS_VERSION:
        return False                       # we know more than we did then
    if entry.get("fingerprint") != _fingerprint(path):
        return False
    if not entry.get("key"):
        return False                       # written before keys existed
    thumb = entry.get("thumb")
    if thumb and not (project / "analysis" / "thumbs" / thumb).exists():
        return False
    proxy = entry.get("proxy")
    if proxy and not (project / proxy).exists():
        return False
    return True


def ingest(project: Path, video_thumbs: int = 6, quiet: bool = False) -> dict:
    media = project / "media"
    if not media.exists():
        raise SystemExit(f"No media folder at {media}. Put your files there.")

    analysis = project / "analysis"
    thumbs = analysis / "thumbs"
    proxies = analysis / "proxies"
    cuts_dir = analysis / "cuts"
    for d in (analysis, thumbs, proxies, cuts_dir):
        d.mkdir(parents=True, exist_ok=True)

    known = STILL_EXT | Shot.VIDEO_EXT | HEIC_EXT
    # media/_unreadable/ is where quarantine() puts videos ingest could
    # not read -- excluded here, or a quarantined file would be found
    # again on the next run and either fail a second time or, worse,
    # get scanned as ordinary footage once it no longer fails.
    in_quarantine = lambda p: bool(set(kinds.ASIDE_DIRNAMES)
                                   & set(p.relative_to(media).parts))
    files = sorted(p for p in media.rglob("*")
                   if p.suffix.lower() in known and not in_quarantine(p))

    # Anything in media/ we are not going to touch. Say so at the end --
    # a file that silently does not appear in the film is the worst kind
    # of bug, because it looks like nothing happened.
    ignored = sorted(p.name for p in media.rglob("*")
                     if p.is_file() and p.suffix.lower() not in known
                     and not in_quarantine(p))
    unreadable: list[str] = []
    quarantined: list[str] = []
    converted = 0
    reused = 0

    # Order. Photographs off a camera are named by a counter that says
    # nothing about the day; the shutter time does. See in_capture_order
    # for why this is all-or-nothing.
    probes = {p: (probe(p) if p.suffix.lower() in Shot.VIDEO_EXT else {})
              for p in files}
    when = {p: taken_at(p, probes[p]) for p in files}
    ordered = in_capture_order(files, when)
    by_time = ordered is not files and ordered != files

    keys = analysis_keys([p.relative_to(project).as_posix() for p in ordered])
    was = _previous(analysis)
    entries: list[dict] = []

    for n, source in enumerate(ordered, 1):
        rel_source = source.relative_to(project).as_posix()
        key = keys[rel_source]

        # Nothing about this file has changed since last time and every
        # derived piece is still on disk. Ingest used to redo all of it
        # on every run -- two full ffmpeg passes over the audio, a cut
        # detection, a proxy, six thumbnails, a motion centroid -- so
        # dropping one clip into a folder of forty cost all forty again.
        old = was.get(rel_source)
        if old is not None and _still_usable(old, project, source):
            entry = dict(old)
            entry["n"] = n
            entry = _top_up_sound(entry, source)
            entries.append(entry)
            reused += 1
            if not quiet:
                print(f"  [{n:2d}/{len(ordered)}] {source.name}   "
                      f"(unchanged)")
            continue

        if not quiet:
            print(f"  [{n:2d}/{len(ordered)}] {source.name}")

        path = source                        # what she actually dropped in
        if path.suffix.lower() in HEIC_EXT:
            jpg = analysis / "converted" / f"{key}.jpg"
            if not convert_heic(path, jpg):
                unreadable.append(path.name)
                continue
            path = jpg                       # from here on, an ordinary jpg
            converted += 1

        rel = path.relative_to(project).as_posix()
        common = {"n": n, "path": rel, "key": key,
                  "fingerprint": _fingerprint(source),
                  "analysis": ANALYSIS_VERSION}
        if when.get(source) is not None:
            common["taken"] = round(when[source], 1)

        if path.suffix.lower() in STILL_EXT:
            img = pix.imread(path, cv2.IMREAD_COLOR)
            if img is None:
                unreadable.append(source.name)
                continue
            focus, how = find_focus(img)
            name = f"{key}.jpg"
            pix.imwrite(thumbs / name, thumb_of(img))
            h, w = img.shape[:2]
            entries.append({
                **common, "kind": "still", "thumb": name,
                "width": w, "height": h, "aspect": round(w / h, 3),
                "focus": [round(focus[0], 3), round(focus[1], 3)],
                "focus_from": how,
                **({"from": rel_source} if path is not source else {}),
            })
        else:
            info = video_info(path)
            if not info["width"] or not info["height"]:
                # ffprobe found no video stream at all -- a moov-less mp4
                # from a recording that was killed rather than stopped
                # cleanly, most often. Photos get exactly this check via
                # imread returning None; video had no equivalent, so this
                # file used to reach make_proxy()'s `check=True` and take
                # the whole ingest down with an unhandled
                # CalledProcessError instead of a clean skip.
                quarantine(path, media)
                unreadable.append(source.name)
                quarantined.append(source.name)
                continue
            proxy = proxies / f"{key}.mp4"
            if not make_proxy(path, proxy):
                # ffprobe was happy and ffmpeg was not. Set it aside the
                # same way, rather than carrying on with no stand-in and
                # failing later, in the middle of a peek.
                quarantine(path, media)
                unreadable.append(source.name)
                quarantined.append(source.name)
                continue
            cuts = detect_cuts(proxy)
            (cuts_dir / f"{key}.json").write_text(
                json.dumps(cuts, indent=1), encoding="utf-8")

            cap = cv2.VideoCapture(str(proxy))
            dur = info["duration"] or 1.0
            first = None
            for k in range(video_thumbs):
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * dur * (k + 0.5) / video_thumbs)
                ok, fr = cap.read()
                if ok:
                    pix.imwrite(thumbs / f"{key}_{k}.jpg", thumb_of(fr, 320))
                    if first is None:
                        first = f"{key}_{k}.jpg"
            cap.release()

            sound = detect_sound(path, info["duration"])
            # Where the person is. Read off the proxy, which is small and
            # already built. Video used to get no focus point at all and
            # scaffold hard-coded the middle of the frame -- which for a
            # 16:9 webcam cropped into a 9:16 film means the crop lands
            # wherever you happened to be sitting.
            spot = speaker_focus(proxy)
            entries.append({
                **common, "kind": "video",
                "thumb": first or "", "proxy": proxy.relative_to(project).as_posix(),
                "cuts": cuts, "sound": sound,
                **({"focus": list(spot), "focus_from": "speaker"}
                   if spot else {}),
                **info,
            })

    contact_sheet(entries, thumbs, analysis / "contact.jpg")

    if by_time and not quiet:
        print("\n  Ordered by when they were taken, not by filename "
              "(every file said).")
    if reused and not quiet:
        print(f"  {reused} file(s) were unchanged and were not looked at "
              f"again.")

    # Printed even when quiet -- `quiet` means "skip the file-by-file
    # listing", not "hide the fact that something of hers is missing".
    if converted:
        print(f"\n  {converted} iPhone photo(s) converted to jpg so they "
              f"can be used (originals untouched).")
    if unreadable:
        print(f"\n  !! {len(unreadable)} file(s) could NOT be read, and are "
              f"not in your film:")
        for nm in unreadable:
            moved = "  (moved to media/_unreadable/)" if nm in quarantined else ""
            print(f"       {nm}{moved}")
        if quarantined:
            print("     A video in that state is not just skipped -- it is "
                  "moved so a\n"
                  "     future ingest does not trip over it again. Nothing "
                  "is deleted; it\n"
                  "     is still in media/_unreadable/ if you want to look "
                  "or try a repair.")
        if len(quarantined) < len(unreadable):
            print("     If these are iPhone photos, the easiest fix is on the "
                  "phone:\n"
                  "     Settings > Camera > Formats > Most Compatible. They "
                  "arrive as\n"
                  "     jpg from then on. For the ones you already have, open "
                  "each in\n"
                  "     Windows Photos and use Save as > JPEG.")
    if ignored:
        shown = ", ".join(ignored[:4]) + ("..." if len(ignored) > 4 else "")
        print(f"\n  {len(ignored)} file(s) in media/ ignored -- not photos "
              f"or clips: {shown}")

    manifest = {"project": project.name, "count": len(entries),
                "converted": converted, "unreadable": unreadable,
                "media": entries}
    (analysis / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def proxy_for(project: Path, src: str) -> str | None:
    """The 480p stand-in for a video, if ingest has made one."""
    p = project / "analysis" / "proxies" / (key_of(project, src) + ".mp4")
    return p.relative_to(project).as_posix() if p.exists() else None
