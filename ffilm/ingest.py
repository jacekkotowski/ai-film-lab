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

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import kinds
from .render import ffmpeg_bin, ffprobe_bin
from .spec import Shot

STILL_EXT = kinds.STILL

# What an iPhone shoots by default. Neither OpenCV nor Pillow can open it,
# so before this existed every iPhone photo dropped into media/ vanished in
# silence -- no error, no mention, just missing from the film.
HEIC_EXT = kinds.HEIC


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


def probe(path: Path) -> dict:
    exe = ffprobe_bin()
    out = subprocess.run(
        [exe, "-v", "error", "-print_format", "json", "-show_format",
         "-show_streams", str(path)],
        capture_output=True, text=True)
    if out.returncode != 0:
        return {}
    return json.loads(out.stdout or "{}")


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
    r = subprocess.run(
        # -map 0:v:0 on purpose: a HEIC can carry more than one image
        # (thumbnails, depth maps, HDR gain maps). Take the first, which is
        # the photo, not whatever ffmpeg decides is "best".
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(src), "-map", "0:v:0", "-frames:v", "1", "-q:v", "2",
         str(dst)],
        capture_output=True, text=True)
    return r.returncode == 0 and dst.exists()


def make_proxy(src: Path, dst: Path, height: int = 480) -> None:
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
         "-vf", f"scale=-2:{height}", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "28", "-g", "12", "-an", str(dst)], check=True)


def loudness(path: Path) -> tuple[float, float] | None:
    """(mean, peak) level of the clip in dBFS, or None if it has no audio."""
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path), "-vn",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode != 0:
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
    """
    lv = loudness(path)
    if lv is None:
        return -32.0
    mean, _peak = lv
    return max(-60.0, min(-30.0, mean - 18.0))


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
    db = silence_floor(path) if floor is None else float(str(floor).rstrip("dB"))
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path), "-vn",
         "-af", f"silencedetect=noise={db}dB:d={min_gap}", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode != 0 or duration <= 0:
        return quiet_none                       # no audio stream at all

    starts = [float(m) for m in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: (-?[0-9.]+)", r.stderr)]

    quiet: list[tuple[float, float]] = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration   # silence running to the end
        quiet.append((max(0.0, s), min(duration, e)))

    ratio = max(0.0, 1.0 - sum(e - s for s, e in quiet) / duration)
    if ratio < 0.02:
        return quiet_none

    # Where the sound actually begins and ends, ignoring lead-in and tail.
    first = quiet[0][1] if quiet and quiet[0][0] <= 0.15 else 0.0
    last = quiet[-1][0] if quiet and quiet[-1][1] >= duration - 0.15 else duration
    inner = [[round(s, 2), round(e, 2)] for s, e in quiet if first < s and e < last]

    return {"has": True, "ratio": round(ratio, 3), "in": round(first, 2),
            "out": round(last, 2), "quiet": inner, "floor_db": round(db, 1)}


def detect_cuts(path: Path, threshold: float = 0.28) -> list[float]:
    """Shot boundaries, in seconds. Run this on the proxy -- much faster."""
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path), "-filter:v",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True)
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
        img = cv2.imread(str(tp))
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
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])


# --------------------------------------------------------------------------
# The main entry point
# --------------------------------------------------------------------------


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
    files = sorted(p for p in media.rglob("*") if p.suffix.lower() in known)

    # Anything in media/ we are not going to touch. Say so at the end --
    # a file that silently does not appear in the film is the worst kind
    # of bug, because it looks like nothing happened.
    ignored = sorted(p.name for p in media.rglob("*")
                     if p.is_file() and p.suffix.lower() not in known)
    unreadable: list[str] = []
    converted = 0

    entries: list[dict] = []

    for n, path in enumerate(files, 1):
        if not quiet:
            print(f"  [{n:2d}/{len(files)}] {path.name}")

        source = path                        # what she actually dropped in
        if path.suffix.lower() in HEIC_EXT:
            jpg = analysis / "converted" / f"{path.stem}.jpg"
            if not convert_heic(path, jpg):
                unreadable.append(path.name)
                continue
            path = jpg                       # from here on, an ordinary jpg
            converted += 1

        rel = path.relative_to(project).as_posix()

        if path.suffix.lower() in STILL_EXT:
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is None:
                unreadable.append(source.name)
                continue
            focus, how = find_focus(img)
            name = f"{n:02d}_{path.stem}.jpg"
            cv2.imwrite(str(thumbs / name), thumb_of(img))
            h, w = img.shape[:2]
            entries.append({
                "n": n, "path": rel, "kind": "still", "thumb": name,
                "width": w, "height": h, "aspect": round(w / h, 3),
                "focus": [round(focus[0], 3), round(focus[1], 3)],
                "focus_from": how,
                **({"from": source.relative_to(project).as_posix()}
                   if source is not path else {}),
            })
        else:
            info = video_info(path)
            proxy = proxies / f"{path.stem}.mp4"
            make_proxy(path, proxy)
            cuts = detect_cuts(proxy)
            (cuts_dir / f"{path.stem}.json").write_text(
                json.dumps(cuts, indent=1), encoding="utf-8")

            cap = cv2.VideoCapture(str(proxy))
            dur = info["duration"] or 1.0
            first = None
            for k in range(video_thumbs):
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * dur * (k + 0.5) / video_thumbs)
                ok, fr = cap.read()
                if ok:
                    cv2.imwrite(str(thumbs / f"{n:02d}_{path.stem}_{k}.jpg"),
                                thumb_of(fr, 320))
                    if first is None:
                        first = f"{n:02d}_{path.stem}_{k}.jpg"
            cap.release()

            sound = detect_sound(path, info["duration"])
            # Where the person is. Read off the proxy, which is small and
            # already built. Video used to get no focus point at all and
            # scaffold hard-coded the middle of the frame -- which for a
            # 16:9 webcam cropped into a 9:16 film means the crop lands
            # wherever you happened to be sitting.
            spot = speaker_focus(proxy)
            entries.append({
                "n": n, "path": rel, "kind": "video",
                "thumb": first or "", "proxy": proxy.relative_to(project).as_posix(),
                "cuts": cuts, "sound": sound,
                **({"focus": list(spot), "focus_from": "speaker"}
                   if spot else {}),
                **info,
            })

    contact_sheet(entries, thumbs, analysis / "contact.jpg")

    # Printed even when quiet -- `quiet` means "skip the file-by-file
    # listing", not "hide the fact that something of hers is missing".
    if converted:
        print(f"\n  {converted} iPhone photo(s) converted to jpg so they "
              f"can be used (originals untouched).")
    if unreadable:
        print(f"\n  !! {len(unreadable)} file(s) could NOT be read, and are "
              f"not in your film:")
        for nm in unreadable:
            print(f"       {nm}")
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
    p = project / "analysis" / "proxies" / (Path(src).stem + ".mp4")
    return p.relative_to(project).as_posix() if p.exists() else None
