"""
pix.py  --  read and write a picture, whatever the file is called.

The whole file exists for one measured fact. On Windows, OpenCV's
`imread` and `imwrite` pass the path to the C runtime in the machine's
ANSI codepage, so a name with a letter that codepage does not have
simply does not open. Measured on this machine, OpenCV 4.14:

    cv2.imwrite("...\\Zdjecia swiateczne\\zdjecie_ace.jpg", img)   -> False
    cv2.imread(same)                                              -> None

No exception either time. `imwrite` returns False, `imread` returns
None, and both look exactly like "that file is corrupt".

What that cost, before this existed:

  * a photograph called `zdjecie.jpg` was reported as one that "could
    NOT be read" and left out of the film -- with the message pointing
    at iPhone HEIC, which was the wrong trail entirely;
  * a project called `Zima nad morzem` -- the example in this toolkit's
    own documentation -- built no thumbnails, no contact sheet, no
    opening card and no cover, and then crashed in `cover.save` on the
    `stat()` of a file `imwrite` had quietly declined to write. After
    the whole of `final` had rendered.

The fix is to do the file half in Python, which speaks Unicode, and
leave OpenCV doing only the codec half:

    read   numpy.fromfile  ->  cv2.imdecode
    write  cv2.imencode    ->  numpy.tofile

Verified on the same path that fails above; both round-trip.

Only stills go through here. `cv2.VideoCapture` was measured on the
same path and opens it correctly -- it reaches ffmpeg, which has always
handled Unicode -- so video is left alone.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def imread(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """A picture as BGR pixels, or None. Same contract as cv2.imread."""
    try:
        raw = np.fromfile(str(path), dtype=np.uint8)
    except (OSError, ValueError):
        return None
    if raw.size == 0:
        return None
    return cv2.imdecode(raw, flags)


def imwrite(path: str | Path, img: np.ndarray,
            params: list[int] | None = None) -> bool:
    """Write a picture. Same contract as cv2.imwrite: True if it landed.

    The suffix chooses the codec, exactly as it does for cv2.imwrite --
    so callers keep naming their files and nothing else changes.
    """
    path = Path(path)
    try:
        ok, buf = cv2.imencode(path.suffix or ".jpg", img, params or [])
    except cv2.error:
        return False
    if not ok:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        buf.tofile(str(path))
    except (OSError, ValueError):
        return False
    return True
