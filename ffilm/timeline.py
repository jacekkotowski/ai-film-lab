"""
timeline.py  --  where every shot sits in the rendered film, for other tools.

`film final` writes it beside the video: out/final.mp4 gets
out/final.timeline.json. It holds only what needs this toolkit's own
rules to work out -- frame-exact times, what each shot is for, a title --
and the keys to everything else: `id` finds the shot in film.yaml, `src`
finds the file in analysis/manifest.json. Paths are relative to the
project folder, as they are in film.yaml.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from . import kinds
from .spec import Film, Shot, frames_for, pretty_name

VERSION = 1


def shot_frames(film: Film) -> list[tuple[int, int]]:
    """(start_frame, end_frame) per shot, end exclusive. The renderer's own
    count, so it cannot drift from the video -- see spec.frames_for."""
    out, at = [], 0
    for s in film.shots:
        n = frames_for(s.duration, film.fps)
        out.append((at, at + n))
        at += n
    return out


def roles(film: Film, card_src: str) -> list[str]:
    """title | intro | slide | closing | clip for each shot.

    A camera take before the first narrated picture is the intro and one
    after the last is the closing -- the order scaffold plays them in.
    With no narrated pictures there is nothing to be before or after, so
    every take is a clip."""
    card = Path(card_src).as_posix()
    slides = [i for i, s in enumerate(film.shots) if s.voice]
    out = []
    for i, s in enumerate(film.shots):
        if Path(s.src).as_posix() == card:
            out.append("title")
        elif s.voice:
            out.append("slide")
        elif s.kind == "video" and slides and i < slides[0]:
            out.append("intro")
        elif s.kind == "video" and slides and i > slides[-1]:
            out.append("closing")
        else:
            out.append("clip")
    return out


def shot_title(film: Film, shot: Shot, role: str) -> str:
    """The film's title on its card; a picture's cleaned filename; for a
    take, whose filename is only a date, its first line said."""
    if role == "title":
        return film.title
    stem = Path(shot.src).stem
    if kinds.is_recording(stem):
        said = next((c.text for c in shot.captions if c.dur > 0), "")
        return said or role.capitalize()
    return pretty_name(kinds.hint(stem)[2]) or role.capitalize()


def slug(name: str) -> str:
    """The project folder's name as the next stage files it:
    "It Reads Us - We Can't Read It" -> "it-reads-us-we-can-t-read-it".
    Written here, once, so ai-3d-studio never guesses its own. NFKD strips
    accents but has no decomposition for the Polish ł, which would vanish
    ("Kołakowski" -> "koakowski"), so it is spelled out first."""
    name = name.replace("ł", "l").replace("Ł", "L")
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "film"


def file_sha256(path: Path) -> str | None:
    """The video's fingerprint. A later stage stores it and compares, so a
    re-render is seen even when the length is unchanged. None when there
    is no file: never worth losing a render over."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def export(film: Film, card_src: str, video_name: str,
           video_sha256: str | None = None) -> dict:
    """The whole timeline as a JSON-able dict. Pure."""
    fps = film.fps
    frames = shot_frames(film)
    shots = []
    for s, role, (a, b) in zip(film.shots, roles(film, card_src), frames):
        start, end = a / fps, b / fps
        shots.append({
            "id": s.id,
            "role": role,
            "title": shot_title(film, s, role),
            "start_frame": a,
            "end_frame": b,
            "start": round(start, 3),
            "end": round(end, 3),
            "kind": s.kind,
            "src": s.src,
            "voice": s.voice,
            "captions": [
                {"text": c.text,
                 "start": round(start + c.at, 3),
                 "end": round(min(end, start + c.at + c.dur), 3)}
                for c in s.captions if c.dur > 0],
        })
    total = frames[-1][1] if frames else 0
    return {
        "version": VERSION,
        "slug": slug(film.root.resolve().name),
        "video": video_name,
        "video_sha256": video_sha256,
        "title": film.title,
        "project_dir": film.root.resolve().as_posix(),
        "fps": fps,
        "width": film.width,
        "height": film.height,
        "frames": total,
        "duration": round(total / fps, 3),
        "shots": shots,
    }


def path_for(video: Path) -> Path:
    return video.with_suffix(".timeline.json")


def write(film: Film, video: Path, card_src: str) -> Path:
    """export(), beside the video. Written whole or not at all: another
    tool may be watching the folder."""
    out = path_for(video)
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(export(film, card_src, video.name, file_sha256(video)),
                               indent=2, ensure_ascii=False),
                    encoding="utf-8")
    part.replace(out)
    return out
