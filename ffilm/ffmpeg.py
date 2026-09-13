"""
ffmpeg.py  --  finding the two outside programs everything else calls.

Analysis, sound, recording and rendering all run ffmpeg. This used to
live in render.py, which meant reading a clip's duration depended on the
renderer. It lives at the bottom now, and knows nothing about films.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit(
            "ffmpeg not found on PATH.\n"
            "Install it with:  winget install --id Gyan.FFmpeg -e\n"
            "then close and reopen your terminal."
        )
    return exe


def ffprobe_bin() -> str:
    """ffprobe, the other half of ffmpeg. It reads durations and sizes.

    Ask PATH for it by name first. The tempting one-liner --
    ffmpeg_bin().replace("ffmpeg", "ffprobe") -- is wrong, and wrong in a
    way that only shows up on the install our own docs recommend: winget
    unpacks into ...\\ffmpeg-9.0.1-full_build\\bin\\ffmpeg.exe, and a blind
    replace renames the FOLDER too. Only ever swap the filename.
    """
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    p = Path(ffmpeg_bin())
    beside = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
    if beside.exists():
        return str(beside)
    raise SystemExit(
        "ffprobe not found on PATH. It ships alongside ffmpeg, so this "
        "usually means a half-finished install:\n"
        "  winget install --id Gyan.FFmpeg -e\n"
        "then close and reopen your terminal."
    )
