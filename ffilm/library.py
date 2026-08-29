"""
library.py  --  the shelf. Things you set up once and never think about again.

A film needs two pieces that are almost never about *this* film: a piece
of background music, and a picture to put the title on. Before this, both
had to be carried into every new project folder by hand -- which meant
that the fastest possible film (talk at the camera, watch it back) still
had two trips through Explorer in the middle of it.

So they live once, here:

    library/
      music/    any audio file. Backs every film that has none of its own.
      cover/    backdrops for the thumbnail. Put in two -- one wide, one
                tall -- and each film takes the one that is its shape.

Nothing in here is ever modified, moved or rendered into a film's folder;
it is read where it lies. A project's own `music/` and `cover/` still
win, so one film wanting its own track stays a matter of dropping the
track in that film's folder.

FFILM_LIBRARY moves the shelf somewhere else -- a synced folder, another
drive. Setting it to nothing at all switches the shelf off, which is what
the tests do so that they do not depend on what is on your disk.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import kinds

README = r"""This folder is your shelf. It is read by EVERY film you make,
so you only have to fill it in once.

  music\   Put a piece of music here -- one file. Every film that does
           not have its own music\ folder uses it: cut to length, faded
           in and out, and turned down while you are talking.

  cover\   Put in two pictures: one WIDE (landscape) and one TALL
           (portrait). When a film needs a thumbnail it takes whichever
           of the two is its shape and prints the film's title on it.
           A .jpg, a .png or a .gif all work.

Several files in either folder is fine -- the first one alphabetically is
used, so putting 01_ in front of a name chooses between them.

To use something different for ONE film, put it in that film's own
music\ or cover\ folder instead. The film's own folder always wins.

Nothing here is ever moved, changed or copied. It is read where it lies.
"""


def root() -> Path:
    """Where the shelf is. Beside the toolkit unless you say otherwise."""
    override = os.environ.get("FFILM_LIBRARY")
    if override is not None:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "library"


def enabled() -> bool:
    """FFILM_LIBRARY set to nothing means: no shelf. Used by the tests, so
    that a film built in a temporary folder cannot pick up your music."""
    return os.environ.get("FFILM_LIBRARY", "x") != ""


def music_dir() -> Path:
    return root() / "music"


def cover_dir() -> Path:
    return root() / "cover"


def ensure() -> Path | None:
    """Make the shelf, and say on it what it is for. Safe to call always.
    None when the shelf is switched off, in which case nothing is made --
    an off switch that still creates two folders is not an off switch."""
    if not enabled():
        return None
    base = root()
    for d in (base / "music", base / "cover"):
        d.mkdir(parents=True, exist_ok=True)
    readme = base / "READ ME.txt"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")
    return base


def _first(folder: Path, exts: set[str]) -> Path | None:
    """First file alphabetically, of the kinds we can use. Alphabetical
    and not newest, because alphabetical is a rule you can steer: put
    01_ in front of the one you want."""
    if not folder.is_dir():
        return None
    found = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in exts)
    return found[0] if found else None


def music() -> Path | None:
    """The shared background track, if there is one."""
    if not enabled():
        return None
    return _first(music_dir(), kinds.AUDIO)


def is_wide(image: Path) -> bool | None:
    """Landscape? None when the file cannot be read as a picture at all.

    Only the header is read, so this stays cheap however large the
    picture is -- and it works for the formats OpenCV cannot open, which
    is the reason a .gif may be a backdrop.
    """
    try:
        from PIL import Image
        with Image.open(image) as im:
            w, h = im.size
    except Exception:
        return None
    return w >= h


def backdrops() -> list[Path]:
    """Every picture on the shelf, alphabetically."""
    if not enabled() or not cover_dir().is_dir():
        return []
    return sorted(p for p in cover_dir().iterdir()
                  if p.is_file() and p.suffix.lower() in kinds.POSTER)


def backdrop(wide: bool) -> Path | None:
    """The shared thumbnail picture of the shape this film is.

    Chosen by measuring the pictures rather than by what they are called,
    because "put in a wide one and a tall one" is an instruction somebody
    can follow while tired, and "name them wide.jpg and tall.jpg" is one
    more thing to get wrong. With only one picture on the shelf, that one
    is used and cropped -- a cover is never letterboxed.
    """
    found = backdrops()
    if not found:
        return None
    matching = [p for p in found if is_wide(p) is wide]
    return matching[0] if matching else found[0]
