"""
kinds.py  --  what counts as a photo, a clip, a track.

One list, imported everywhere. It used to be five: the audio extensions
alone were written out in guide.py, scaffold.py, voice.py and inline in
cli.py, which is exactly the shape of bug that hurts most here -- add
.opus one day, fix three of the four, and a file quietly does not appear
in someone's film with nothing on screen to say why.

Adding a format is now one line in this file.
"""

from __future__ import annotations

from pathlib import Path

STILL = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}

# What an iPhone shoots by default. Converted to jpg on ingest, because
# neither OpenCV nor Pillow can open it.
HEIC = {".heic", ".heif"}

VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts"}

AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# Everything that belongs in media/ -- the picture side of a film.
MEDIA = STILL | HEIC | VIDEO

# What may sit behind a title on a thumbnail. A superset of STILL, and
# deliberately NOT part of it: a .gif in media/ would be found by ingest
# and turned into a shot, and OpenCV cannot decode one, so that shot
# would be a hole in the film. A cover is drawn through Pillow as well,
# which can, so on that one path a .gif is fine -- animation ignored,
# first frame used.
POSTER = STILL | {".gif"}


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO


def is_still(path: str | Path) -> bool:
    return Path(path).suffix.lower() in STILL | HEIC


def is_audio(path: str | Path) -> bool:
    return Path(path).suffix.lower() in AUDIO


def is_media(path: str | Path) -> bool:
    return Path(path).suffix.lower() in MEDIA
