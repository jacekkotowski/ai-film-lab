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

import re
from pathlib import Path

STILL = {".jpg", ".jpeg", ".jfif", ".png", ".tif", ".tiff", ".webp", ".bmp"}

# What an iPhone shoots by default. Converted to jpg on ingest, because
# neither OpenCV nor Pillow can open it.
HEIC = {".heic", ".heif"}

VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts"}

AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

# Everything that belongs in media/ -- the picture side of a film.
MEDIA = STILL | HEIC | VIDEO

# The one folder inside media/ that is not material. `ingest` moves a
# file it cannot read in here rather than deleting it, so ANYTHING that
# scans media/ has to skip it -- and this lives here, with the rest of
# the shared vocabulary, because it did not: ingest skipped it and the
# guide did not, so the guide counted a broken take as footage and sent
# somebody to `init`, which cannot write a film with no shots in it.
UNREADABLE_DIRNAME = "_unreadable"

# The other one: a take you fluffed and asked to record again. Same
# rule -- inside media/, skipped by everything that scans it, and moved
# rather than deleted, so pressing the wrong button costs nothing.
DISCARDED_DIRNAME = "_discarded"

# Everything inside media/ that is NOT material.
ASIDE_DIRNAMES = (UNREADABLE_DIRNAME, DISCARDED_DIRNAME)


def is_aside(path: str | Path, media: str | Path) -> bool:
    """Is this file in one of the folders inside media/ that is not
    material -- a take you discarded, a file that could not be read?

    A function and not four separate re-implementations of the same
    `set(...) & set(...)`, because that is exactly how the rule got
    applied in some scans and not others: ingest skipped them, the guide
    counted them as footage, `scaffold` picked a discarded take's audio
    as the film's narration, and `voice` transcribed a fluffed take and
    captioned its words onto the good one.
    """
    try:
        parts = Path(path).relative_to(media).parts
    except ValueError:
        return False
    return bool(set(ASIDE_DIRNAMES) & set(parts))

# What may sit behind a title on a thumbnail. A superset of STILL, and
# deliberately NOT part of it: a .gif in media/ would be found by ingest
# and turned into a shot, and OpenCV cannot decode one, so that shot
# would be a hole in the film. A cover is drawn through Pillow as well,
# which can, so on that one path a .gif is fine -- animation ignored,
# first frame used.
POSTER = STILL | {".gif"}

# What a file made by `film record` is called. Here and not in record.py
# because spec.py needs it too, and spec sits below record: bokeh is on
# for YOUR takes by default, not for every clip -- a clip with nobody in
# it would have its whole picture blurred.
REC_PREFIX = "rec_"


# A number in front of a filename means "play it here" -- see
# scaffold._hint, which strips one before reading the rest of the name.
# It lives here, at the bottom, because `is_recording` has to strip the
# same one: see there.
#
# `(?!\d)` keeps a date or a camera counter out of it: `20260917.jpg`
# and `IMG_0042.jpg` are not somebody asking for position 202 or 42.
NUM_PREFIX = re.compile(r"^(\d{1,3})(?!\d)[_.\-\s]*")


def is_recording(stem: str) -> bool:
    """Was this file made by `film record`?

    A number you put in front is stripped first. Numbering a take is the
    one way of saying where it should play, and on 2026-09-20 doing it
    stopped the file being a take at all: the 1.2x speed, the sharpening
    and the bokeh are all switched on by this one answer, so an intro
    dragged to the front of a film quietly lost all three. A close_ in
    front (a recorded closing, see CLOSE_PREFIX) is stripped the same way.
    """
    s = NUM_PREFIX.sub("", stem.lower())
    if s.startswith(CLOSE_PREFIX):
        s = s[len(CLOSE_PREFIX):]
    return s.startswith(REC_PREFIX)


# `film record --closing` names its take close_rec_...: scaffold._hint
# reads close_ as "play last", so the closing stays last even when the
# narration is retaken after it. Found 2026-09-23: placed by time alone,
# a closing recorded before a narration retake became a second intro.
CLOSE_PREFIX = "close_"


# What a microphone-only take (`film record --voice`) is called. Its own
# prefix, not REC_PREFIX -- a voiceover is narration read over pictures,
# not a talking-head clip, and REC_SPEED (scaffold's 1.2x for `rec_*`)
# has no business touching somebody's spoken narration. voice.py matches
# on this as a PREFIX, so a dated file still counts.
VOICEOVER_PREFIX = "voiceover_"


def pick_narration(paths, when=None) -> Path | None:
    """Which of these files is the film's narration. Pure, given `when`.

    Audio only -- the recording window writes `voiceover_....cues.json`
    beside a take, and it is not a narration. A file named `voiceover`
    beats any other audio: somebody who names a file that means it. And
    among those, the one written MOST RECENTLY wins, because recording
    again is how anybody says "not that one, this one".

    It used to be the first in alphabetical order, in two places. On
    2026-09-18 that built test_story from the previous day's take while
    the one just recorded, and every press of Next in it, sat unused.

    `when(path)` is the file's time; the file's own modified time unless
    a caller (a test) says otherwise. Ties go to the later name, which
    for dated takes is the later take.
    """
    when = when or (lambda p: Path(p).stat().st_mtime)
    audio = [Path(p) for p in paths if Path(p).suffix.lower() in AUDIO]
    if not audio:
        return None
    named = [p for p in audio if p.name.lower().startswith("voiceover")]
    pool = named or audio
    return max(pool, key=lambda p: (when(p), p.name))


def older_narrations(paths, keep: Path) -> list[Path]:
    """The narration takes a new one replaces, with their cues beside
    them. Only files named voiceover_ -- never music, which is audio too.

    The film already used only the newest; the rest stayed in media/,
    six of them in Turn Heat Into Images on 2026-09-23, alike by name
    and 139 MB between them."""
    paths = [Path(p) for p in paths]
    old = [p for p in paths if p.suffix.lower() in AUDIO
           and p.name.lower().startswith(VOICEOVER_PREFIX)
           and p.name != Path(keep).name]
    stems = {p.stem + "." for p in old}
    cues = [p for p in paths if p.suffix.lower() not in AUDIO
            and any(p.name.startswith(s) for s in stems)]
    return old + cues


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO


def is_still(path: str | Path) -> bool:
    return Path(path).suffix.lower() in STILL | HEIC


def is_audio(path: str | Path) -> bool:
    return Path(path).suffix.lower() in AUDIO


def is_media(path: str | Path) -> bool:
    return Path(path).suffix.lower() in MEDIA
