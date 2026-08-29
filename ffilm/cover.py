"""
cover.py  --  the miniature. The still that makes somebody press play.

The cover proper is not in the film: no duration, no shot, no place on
the timeline -- a picture you upload next to the finished mp4. That is
the whole reason it gets its own folder: an image dropped in `media/`
would be found by `ingest` and dutifully turned into a three-second shot
in the middle of your film. `cover/` is not scanned by anything, so
nothing can happen to it by accident.

The one thing here that IS in the film is the opening card (`build_card`
and below) -- the same picture with the same words, written into
analysis/ so that film.yaml can point at it as an ordinary still. It is
still not made from `cover/` by accident: it is made because a shot in
film.yaml asks for it, and you can delete that shot.

There are two folders it may come from, and the difference is the whole
design. This film's own `cover/` is for a picture chosen FOR this film,
so its filename is taken as the title. `library/cover/` is the shelf --
one landscape picture and one portrait one, filled in once, used by
every film you will ever make. On that path nobody chooses anything: the
picture is whichever of the two is the film's shape, and the title is
what the film is called.

Deliberately thin. The type is drawn by `render.draw_captions` -- the
same font, the same shadow, the same wrapping as the words in the film
itself, because a cover set in a different face than the thing it
introduces looks like somebody else made it.

    uv run film cover                       the film's name on the shelf picture
    uv run film cover --title "Kolobrzeg"   or say the words here
    uv run film cover --wide                16:9 instead of the film's shape

`film final` builds one on its own when there is a picture to build it
on, so in the ordinary case this command is never typed at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import kinds
from .spec import headers, pretty_name, title_of

# YouTube rejects a custom thumbnail over 2MB. Being told that by a web
# form after the render, the upload and the description is a bad moment,
# so the file is brought under the limit here instead.
MAX_BYTES = 2_000_000

# 1280x720 is what YouTube asks for. A vertical project gets the film's
# own shape instead, because a 16:9 cover on a Short is centre-cropped by
# the platform and loses whichever side the title was on.
WIDE = (1280, 720)

# The title sits over a picture that was not chosen for its contrast, so
# it gets a gradient behind it, fading out just above the type. Without
# this, white letters over a bright sky are a rumour.
SCRIM_STRENGTH = 0.78
SCRIM_FADE = 0.9           # gradient height, in multiples of the text block

# A cover is not a caption. Captions are set small and loose because they
# sit under moving pictures and are read in passing; a title is read at
# thumbnail size, in a grid, in about a fifth of a second. So it is set
# as large as will fit and led tightly, which is the difference between
# a poster and a screenshot with words on it.
TITLE_MAX_WIDTH = 0.86
TITLE_LINE_SPACING = 1.04
TITLE_MAX_LINES = 3
TITLE_START = 0.17         # first size tried, as a fraction of the height
TITLE_MARGIN = 0.07        # from the edge the title sits against

# The width alone is not enough of a constraint: the biggest type that
# fits three lines is one word per line filling the whole frame, which
# is a ransom note. Capping how much of the height the block may take
# is what makes it break into sensible phrases instead.
TITLE_MAX_BLOCK = 0.30


def cover_dir(project: Path) -> Path:
    return project / "cover"


@dataclass
class Backdrop:
    """The picture a title is printed on, and where it came from.

    Where it came from is not bookkeeping: a picture in THIS film's
    cover/ folder was put there for this film, so its filename is a
    good guess at the title. A picture on the shared shelf backs every
    film there will ever be, so its filename means nothing here.
    """

    path: Path | None = None
    shared: bool = False

    @property
    def name(self) -> str:
        return self.path.name if self.path else ""


def find_image(project: Path, given: str | None = None) -> Path | None:
    """The picture in THIS project's cover/ folder. One folder, first
    file, alphabetical -- so `01_` in front of a filename picks between
    two of them."""
    if given:
        p = Path(given)
        if not p.is_absolute():
            p = project / given
        if not p.exists():
            raise SystemExit(f"No such image: {p}")
        return p
    d = cover_dir(project)
    if not d.is_dir():
        return None
    stills = sorted(p for p in d.iterdir()
                    if p.is_file() and p.suffix.lower() in kinds.POSTER)
    return stills[0] if stills else None


def choose(project: Path, given: str | None = None,
           wide: bool = True) -> Backdrop:
    """The picture to build on: this film's own, else the shared shelf.

    `wide` is the shape of the film, and it only matters on the shelf --
    where the whole idea is that you put in one landscape picture and
    one portrait one, and never think about it again.
    """
    own = find_image(project, given)
    if own is not None:
        return Backdrop(own, shared=False)
    from . import library
    return Backdrop(library.backdrop(wide), shared=True)


def title_from(backdrop: Backdrop, given: str | None, project: Path) -> str:
    """The words on the thumbnail, most deliberate answer first.

    `--title` is somebody typing it now. `title:` in film.yaml is
    somebody having typed it once. A picture dropped into this film's own
    cover/ folder was named by hand and is usually already the words. And
    failing all three, the film is called what its folder is called --
    which is the automatic path, and the one nobody has to know about.
    """
    if given is not None:
        return given
    said = headers(project / "film.yaml").get("title")
    if said:
        return str(said)
    if backdrop.path is not None and not backdrop.shared:
        return pretty_name(backdrop.path.stem)
    return title_of(project)


def out_path(project: Path) -> Path:
    return project / "out" / "cover.jpg"


# The opening shot: the same picture and the same words as the thumbnail,
# written out where the film can use it as an ordinary still. It lives in
# analysis/ because it is DERIVED -- like a proxy, like a converted HEIC.
# Nothing is lost by deleting it; it is made again on the next render.
CARD = "title.jpg"


def card_path(project: Path) -> Path:
    return project / "analysis" / CARD


def card_src(project: Path) -> str:
    """How the card is referred to in film.yaml."""
    return card_path(project).relative_to(project).as_posix()


def build_card(project: Path, width: int, height: int,
               font: str | None = None) -> Path | None:
    """Make the opening card. None when there is no picture to make it
    from -- a film that opens on a title over black is a thing somebody
    might choose, but not a thing to hand them unasked.

    Deliberately the same picture, the same words and the same position
    as the thumbnail: somebody who clicks the miniature should land on
    the frame they clicked. That is the whole effect, and it is free.
    """
    back = choose(project, wide=width >= height)
    if back.path is None:
        return None
    frame = compose(back.path, title_from(back, None, project),
                    width, height, "bottom", font)
    out = card_path(project)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return out


def refresh_card(project: Path, width: int, height: int,
                 font: str | None = None) -> Path | None:
    """Rebuild the card if the film has moved on without it.

    Called before every render, because the two ways this goes wrong are
    both silent: analysis/ is derived and gets deleted, which would leave
    film.yaml pointing at nothing; and the title can be changed in
    film.yaml, which would leave the film opening on the old one.
    """
    card = card_path(project)
    try:
        mine = card.stat().st_mtime
    except OSError:
        mine = 0.0
    try:
        edited = (project / "film.yaml").stat().st_mtime
    except OSError:
        edited = 0.0
    if mine and mine >= edited:
        return card
    return build_card(project, width, height, font)


def is_stale(project: Path) -> bool:
    """Should the thumbnail be built again?

    Yes when there is none, and yes when it is older than the film it
    belongs to -- a thumbnail whose title no longer matches the film is
    worse than no thumbnail. No when it is newer, which is what protects
    one you made by hand with --title from being quietly replaced by the
    default the next time you render.
    """
    def when(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    mine = when(out_path(project))
    if not mine:
        return True
    return mine < when(project / "film.yaml")


def read(image: Path) -> np.ndarray:
    """A picture, as BGR pixels.

    OpenCV first because it is what the rest of the toolkit uses, then
    Pillow -- which reads the formats OpenCV will not, .gif above all.
    Somebody who has one good picture and it happens to be a gif should
    not have to find that out from an error message.
    """
    img = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if img is not None:
        return img
    try:
        from PIL import Image
        with Image.open(image) as im:
            rgb = np.array(im.convert("RGB"))
        return rgb[..., ::-1].copy()               # RGB -> BGR
    except Exception:
        raise SystemExit(
            f"Could not open {image.name}. Is it really a picture?")


def fill(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Cover-crop: fill the frame completely, crop the overflow, never
    letterbox. A cover with black bars reads as a mistake."""
    H, W = img.shape[:2]
    scale = max(w / W, h / H)
    new = (max(w, int(round(W * scale))), max(h, int(round(H * scale))))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    img = cv2.resize(img, new, interpolation=interp)
    y = (img.shape[0] - h) // 2
    x = (img.shape[1] - w) // 2
    return img[y:y + h, x:x + w]


def layout_title(draw, text: str, w: int, h: int, font_override: str | None):
    """The biggest type that still fits, and the lines it breaks into.

    Sized down from too-big rather than up from a guess, so a two-word
    title comes out big and a sentence comes out readable, without
    anybody choosing a number.
    """
    from .render import line_height, load_font, wrap_to_width

    max_px = w * TITLE_MAX_WIDTH
    max_block = h * TITLE_MAX_BLOCK
    size = max(14, int(h * TITLE_START))
    while size > 14:
        font = load_font(size, font_override)
        lines = wrap_to_width(draw, text, font, max_px)
        lh = line_height(font)
        block = int(lh * TITLE_LINE_SPACING) * (len(lines) - 1) + lh
        if (len(lines) <= TITLE_MAX_LINES
                and block <= max_block
                and all(draw.textlength(ln, font=font) <= max_px
                        for ln in lines)):
            return font, lines
        size = int(size * 0.94)
    font = load_font(14, font_override)
    return font, wrap_to_width(draw, text, font, max_px)


def scrim(frame: np.ndarray, top: int, bottom: int) -> np.ndarray:
    """Darken the band the type sits in, fading out above it.

    Tied to where the text actually landed rather than to a fixed
    fraction of the frame -- a one-line title over a bright sky needs
    the gradient in a different place than a three-line one.
    """
    h, w = frame.shape[:2]
    block = max(1, bottom - top)
    fade = int(block * SCRIM_FADE)
    mask = np.zeros(h, dtype=np.float32)
    mask[max(0, top):] = SCRIM_STRENGTH
    start = max(0, top - fade)
    if top > start:
        mask[start:top] = (np.linspace(0.0, 1.0, top - start,
                                       dtype=np.float32) ** 2
                           ) * SCRIM_STRENGTH
    return (frame.astype(np.float32) * (1.0 - mask[:, None, None])
            ).clip(0, 255).astype(np.uint8)


def compose(image: Path | None, title: str, w: int, h: int,
            pos: str = "bottom", font: str | None = None) -> np.ndarray:
    """Picture, gradient, title. In that order."""
    from PIL import Image, ImageDraw

    if image is None:
        frame = np.zeros((h, w, 3), dtype=np.uint8)
    else:
        frame = fill(read(image), w, h)

    if not title.strip():
        return frame

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    face, lines = layout_title(d, title, w, h, font)

    from .render import line_height
    lh = line_height(face)
    step = int(lh * TITLE_LINE_SPACING)
    block_h = step * (len(lines) - 1) + lh
    margin = int(h * TITLE_MARGIN)
    if pos == "top":
        y0 = margin
    elif pos == "center":
        y0 = (h - block_h) // 2
    else:
        y0 = h - margin - block_h

    frame = scrim(frame, y0 - int(lh * 0.3), y0 + block_h)

    left_aligned = pos == "lower_third"
    x_margin = w * (1.0 - TITLE_MAX_WIDTH) / 2
    for i, ln in enumerate(lines):
        lw = d.textlength(ln, font=face)
        x = x_margin if left_aligned else (w - lw) / 2
        y = y0 + i * step
        # Heavier than a caption's shadow. A thumbnail is looked at
        # small, next to eleven other thumbnails.
        off = max(2, int(lh * 0.035))
        d.text((x + off, y + off), ln, font=face, fill=(0, 0, 0, 170))
        d.text((x, y), ln, font=face, fill=(255, 255, 255, 255))

    rgba = np.array(layer)
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3][..., ::-1].astype(np.float32)      # RGB -> BGR
    return np.clip(frame.astype(np.float32) * (1 - a) + rgb * a,
                   0, 255).astype(np.uint8)


def save(frame: np.ndarray, out: Path) -> int:
    """Write it, and keep shrinking the quality until it is small enough
    to actually upload."""
    out.parent.mkdir(parents=True, exist_ok=True)
    for quality in (92, 85, 78, 70, 60):
        cv2.imwrite(str(out), frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        size = out.stat().st_size
        if size <= MAX_BYTES:
            return size
    return out.stat().st_size
