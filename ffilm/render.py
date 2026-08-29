"""
render.py  --  turning the spec into pixels.

The pipeline for one output frame:

    source image/frame
      -> prescale once to a sane working size   (quality + speed)
      -> affine warp through the crop window    (the camera move)
      -> average N sub-frames                   (shutter / motion blur)
      -> downsample from the supersample buffer (clean edges)
      -> grade + vignette + grain               (the look)
      -> captions
      -> raw bytes into ffmpeg's stdin

Three quality tiers, same code path. That matters: what you judge in
`peek` is the same edit you ship in `final`, only smaller.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .moves import window_at, window_past_end
from .spec import Caption, Film, Look, Shot, Window

# --------------------------------------------------------------------------
# Quality tiers
# --------------------------------------------------------------------------


@dataclass
class Quality:
    name: str
    height: int | None      # None = use the film's own resolution
    fps: int | None
    supersample: int        # render at Nx then shrink. 2 = clean edges.
    shutter: int            # sub-frames averaged. 4 = real motion blur.
    crf: int
    preset: str
    interp: int

    @property
    def is_final(self) -> bool:
        return self.name == "final"


# Note on `supersample` vs `shutter`: they overlap. Averaging 4 sub-frames
# at slightly different camera positions already anti-aliases, and
# `prepare_source` has pre-reduced the source with INTER_AREA. So final
# uses shutter alone -- supersampling on top of it costs 4x for almost
# nothing. Pass --supersample 2 if you disagree on a particular film.
PEEK = Quality("peek", 360, 4, 1, 1, 32, "ultrafast", cv2.INTER_LINEAR)
DRAFT = Quality("draft", 540, 12, 1, 1, 26, "veryfast", cv2.INTER_LINEAR)
FINAL = Quality("final", None, None, 1, 4, 17, "medium", cv2.INTER_CUBIC)

QUALITIES = {"peek": PEEK, "draft": DRAFT, "final": FINAL}


# --------------------------------------------------------------------------
# The camera: an affine warp through a crop window
# --------------------------------------------------------------------------


def warp(src: np.ndarray, win: Window, ow: int, oh: int, interp: int) -> np.ndarray:
    """Sample the source image through `win` into an ow x oh frame.

    This is the single most important function in the toolkit, and it is
    twelve lines. `win.cx/cy` pick the centre, `win.scale` the tightness,
    `win.roll` the tilt. Sub-pixel accurate, which is why the motion is
    smooth instead of steppy.
    """
    H, W = src.shape[:2]
    aspect = ow / oh

    # Largest window of the output aspect that fits the source, then zoomed.
    w0 = min(W, H * aspect)
    h0 = w0 / aspect
    w = w0 / max(win.scale, 0.01)
    h = h0 / max(win.scale, 0.01)

    # Keep the window inside the image, allowing for the roll.
    th = math.radians(win.roll)
    ext_x = abs(w / 2 * math.cos(th)) + abs(h / 2 * math.sin(th))
    ext_y = abs(w / 2 * math.sin(th)) + abs(h / 2 * math.cos(th))
    cx = float(np.clip(win.cx * W, ext_x, max(ext_x, W - ext_x)))
    cy = float(np.clip(win.cy * H, ext_y, max(ext_y, H - ext_y)))

    cos, sin = math.cos(th), math.sin(th)

    def corner(dx, dy):
        return [cx + dx * cos - dy * sin, cy + dx * sin + dy * cos]

    src_pts = np.float32([corner(-w / 2, -h / 2),
                          corner(+w / 2, -h / 2),
                          corner(-w / 2, +h / 2)])
    dst_pts = np.float32([[0, 0], [ow, 0], [0, oh]])
    M = cv2.getAffineTransform(src_pts, dst_pts)
    return cv2.warpAffine(src, M, (ow, oh), flags=interp,
                          borderMode=cv2.BORDER_REPLICATE)


# How soft the background is, as a fraction of the frame width.
FILL_BLUR = 0.045

# How bright the background sits, as a fraction of the SUBJECT's
# brightness -- not as a fixed multiplier on itself.
#
# A flat multiplier cannot know what it grabbed. The background is the
# part of the frame the crop threw away, which for a person at a desk is
# ceiling and wall: already the darkest thing in the picture. Multiplying
# that by 0.62 measured 41 against a subject at 98, and 41 does not read
# as a room, it reads as a black bar. Levelling against the subject
# instead gives the same look on a bright kitchen and a dim bedroom.
FILL_LEVEL = 0.70
FILL_MIN_GAIN = 0.30      # never crush it below this, whatever the maths
FILL_MAX_GAIN = 1.0       # and never brighten it past what was really there


def blurred_fill(src: np.ndarray, win: Window, ow: int, oh: int,
                 interp: int, aspect: float) -> np.ndarray:
    """The picture whole, on a blurred enlargement of itself.

    Two passes of the same camera through the same window, into two
    different shapes: the frame's shape for the background, and
    `aspect` for the sharp picture that sits on top. Because both use
    the same window, the camera still moves, and it moves the subject
    and the background together.

    The background is blurred at 1/8 scale and enlarged back. A true
    Gaussian at this radius over a 1080x1920 frame costs more than the
    rest of the render put together, and at this softness nobody can
    tell the difference.
    """
    inner_h = int(round(ow / max(aspect, 0.01)))
    inner_h -= inner_h % 2
    if inner_h >= oh:
        # Nothing would show around it. A film that asked for blur and
        # got a plain crop is better than one with a one-pixel halo.
        return warp(src, win, ow, oh, interp)

    inner = warp(src, win, ow, inner_h, interp)
    back = warp(src, win, ow, oh, interp)
    sw, sh = max(8, ow // 8), max(8, oh // 8)
    small = cv2.resize(back, (sw, sh), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigmaX=max(1.0, ow * FILL_BLUR / 8))

    # Measured on the STRIPS THAT SHOW, not on the whole background.
    # The middle of the background is hidden behind the sharp picture and
    # is the brightest part of it -- averaging that in gives back almost
    # exactly the flat multiplier this replaced, which is how the first
    # attempt at this changed 41.6 to 41.4 and fixed nothing.
    top = (oh - inner_h) // 2
    t = int(sh * top / oh)
    b = int(sh * (top + inner_h) / oh)
    strips = np.concatenate([small[:t].reshape(-1, 3),
                             small[b:].reshape(-1, 3)]) if t or b < sh else small
    gain = FILL_LEVEL * float(inner.mean()) / max(float(strips.mean()), 1.0)
    gain = min(FILL_MAX_GAIN, max(FILL_MIN_GAIN, gain))

    back = cv2.resize(small, (ow, oh), interpolation=cv2.INTER_LINEAR)
    back = (back.astype(np.float32) * gain).astype(np.uint8)
    back[(oh - inner_h) // 2:(oh - inner_h) // 2 + inner_h] = inner
    return back


def compose(src: np.ndarray, win: Window, ow: int, oh: int, interp: int,
            film, shot) -> np.ndarray:
    """One finished picture, cropped to the frame or laid on blur."""
    mode = shot.fill or film.fill
    if mode == "blur":
        return blurred_fill(src, win, ow, oh, interp, film.fill_aspect)
    return warp(src, win, ow, oh, interp)


def should_memoise(shot) -> bool:
    """May a rendered frame of this shot be reused for the next one?

    Only for a photograph, and the rule is not a performance judgement --
    it is a correctness one. A clip's picture changes 25 times a second
    on its own, so reusing a frame freezes it. There is no cheap key that
    says "the video has not moved", because the video has always moved.
    """
    return shot.kind == "still"


def motion_px(shot, i: int, n: int, seed: int, ow: int, oh: int) -> float:
    """Roughly how many output pixels the picture travels during frame i.

    Used to pick the shutter adaptively. A slow contemplative drift moves
    well under a pixel per frame -- blurring it four ways is pure waste.
    A punch-in can move ten, and there the blur is the whole point.
    """
    a = window_at(shot, i / n, seed)
    b = window_at(shot, min(1.0, (i + 1) / n), seed)
    s = max(a.scale, 0.01)
    trans = math.hypot((b.cx - a.cx) * ow * s, (b.cy - a.cy) * oh * s)
    zoom = (ow / 2.0) * abs(b.scale - a.scale) / s
    roll = (ow / 2.0) * abs(math.radians(b.roll - a.roll))
    return trans + zoom + roll


def prepare_source(img: np.ndarray, ow: int, oh: int, max_scale: float) -> np.ndarray:
    """Shrink a huge source once, up front, instead of per frame.

    A 45-megapixel photograph warped straight to 1080p aliases badly and
    is slow. Pre-reducing with INTER_AREA is both faster and sharper.
    """
    H, W = img.shape[:2]
    need_w = ow * max_scale * 1.15
    need_h = oh * max_scale * 1.15
    factor = min(W / need_w, H / need_h)
    if factor <= 1.05:
        return img
    new = (max(2, int(W / factor)), max(2, int(H / factor)))
    return cv2.resize(img, new, interpolation=cv2.INTER_AREA)


# --------------------------------------------------------------------------
# Sources: stills and video both become "give me the frame at time t"
# --------------------------------------------------------------------------


class StillSource:
    def __init__(self, path: Path, ow: int, oh: int, max_scale: float):
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise SystemExit(f"Could not read image: {path}")
        self.img = prepare_source(img, ow, oh, max_scale)

    def frame(self, t: float) -> np.ndarray:
        return self.img

    def close(self) -> None:
        pass


class VideoSource:
    """Sequential reader with a cursor. Seeking backwards is rare, so we
    optimise for the common case: walking forward through the clip."""

    def __init__(self, path: Path, shot: Shot, ow: int, oh: int, max_scale: float):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open video: {path}")
        self.src_fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.shot = shot
        self.ow, self.oh, self.max_scale = ow, oh, max_scale
        self.cursor = -1
        self.last: np.ndarray | None = None
        start = int(round(shot.tin * self.src_fps))
        if start > 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            self.cursor = start - 1

    def frame(self, t: float) -> np.ndarray:
        target = int(round((self.shot.tin + t * self.shot.speed) * self.src_fps))
        if target < self.cursor:                 # backwards: re-seek
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            self.cursor = target - 1
        ran_out = False
        while self.cursor < target:
            if not self.cap.grab():
                ran_out = True
                break
            self.cursor += 1
        # Retrieving after a FAILED grab is meaningless, and OpenCV says
        # so in five lines of C++ error straight to stderr, over the top
        # of the progress bar -- which looks exactly like a crash to
        # somebody watching their own film render. Hold the last frame
        # instead, quietly. Asking a hair past the last frame is normal:
        # a container is routinely a fraction longer than its picture.
        ok, img = (False, None) if ran_out else self.cap.retrieve()
        if not ok or img is None:
            if self.last is None:
                raise SystemExit(f"Ran out of video in {self.shot.src}")
            return self.last
        self.last = prepare_source(img, self.ow, self.oh, self.max_scale)
        return self.last

    def close(self) -> None:
        self.cap.release()


def open_source(film: Film, shot: Shot, ow: int, oh: int, max_scale: float):
    path = film.resolve(shot.src)
    if shot.kind == "video":
        return VideoSource(path, shot, ow, oh, max_scale)
    return StillSource(path, ow, oh, max_scale)


# --------------------------------------------------------------------------
# The look
# --------------------------------------------------------------------------


_cache: dict = {}


def _tone_lut(contrast: float, lift: float) -> np.ndarray:
    """Contrast and lift are per-channel curves, so they collapse into a
    single 256-entry lookup table. Applying a LUT is essentially free."""
    key = ("lut", round(contrast, 4), round(lift, 4))
    if key not in _cache:
        x = np.arange(256, dtype=np.float32) / 255.0
        y = (x - 0.5) * contrast + 0.5
        y = y * (1.0 - lift) + lift
        _cache[key] = np.clip(y * 255.0, 0, 255).astype(np.uint8)
    return _cache[key]


def _vignette(w: int, h: int, strength: float) -> np.ndarray:
    """Static per-pixel mask, so build it once and keep it as uint8."""
    key = ("vig", w, h, round(strength, 3))
    if key not in _cache:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / math.sqrt(2)
        m = 1.0 - strength * np.clip(r, 0, 1) ** 2.2
        m8 = np.clip(m * 255.0, 0, 255).astype(np.uint8)
        _cache[key] = cv2.cvtColor(m8, cv2.COLOR_GRAY2BGR)
    return _cache[key]


# Grain is regenerated from a small pool rather than sampled every frame.
# Real film grain is not pixel-sharp anyway, so we build it at half
# resolution and scale up -- cheaper AND more convincing.
_GRAIN_TILES = 8


def _grain(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    key = ("grain", w, h)
    if key not in _cache:
        tiles = []
        for _ in range(_GRAIN_TILES):
            n = rng.standard_normal((max(2, h // 2), max(2, w // 2))).astype(np.float32)
            n = cv2.resize(n, (w, h), interpolation=cv2.INTER_LINEAR)
            tiles.append(n)
        _cache[key] = tiles
    tiles = _cache[key]
    return tiles[int(rng.integers(0, len(tiles)))]


# Midtones take more grain than the extremes, which is what film does.
_MID = np.clip((1.0 - np.abs(np.arange(256) / 255.0 - 0.5) * 1.4) * 255,
               0, 255).astype(np.uint8)


def _glow(frame: np.ndarray, strength: float) -> np.ndarray:
    """Lift shadow detail without washing out highlights or shifting
    color -- this is the practical meaning of "improve the lighting" on
    footage you can't reshoot.

    A shadow-targeted tone curve does the actual lifting (this is what
    reliably brightens dark areas, including flat ones -- local-contrast
    tools like CLAHE only respond to texture, so they do nothing to a
    flat dark wall or a underexposed sky, which is often exactly what
    needs lifting). A small unsharp-mask pass on top adds back the
    sense of depth the flat lift would otherwise remove.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    x = np.arange(256, dtype=np.float32) / 255.0
    # Lift shadows a lot, midtones a little, leave highlights alone --
    # a smooth curve, not a hard threshold, so there's no banding.
    lift_curve = x + strength * 0.5 * np.exp(-((x - 0.12) ** 2) / (2 * 0.16 ** 2))
    lut = np.clip(lift_curve * 255.0, 0, 255).astype(np.uint8)
    l2 = cv2.LUT(l, lut)

    blur = cv2.GaussianBlur(l2, (0, 0), sigmaX=max(l.shape) / 90.0)
    l3 = cv2.addWeighted(l2, 1.0 + 0.25 * strength, blur, -0.25 * strength, 0)

    return cv2.cvtColor(cv2.merge([l3, a, b]), cv2.COLOR_LAB2BGR)


_scratch_cache: dict = {}


def _scratches(w: int, h: int, rng: np.random.Generator,
               strength: float) -> np.ndarray:
    """A handful of thin vertical streaks, repositioned every call so
    they don't sit in the same place for the whole shot -- real film
    damage drifts frame to frame."""
    n_lines = max(1, int(strength * 5))
    mask = np.zeros((h, w), np.uint8)
    for _ in range(n_lines):
        x = int(rng.integers(0, w))
        thickness = 1 if rng.random() < 0.7 else 2
        alpha = rng.uniform(0.15, 0.5) * strength
        length = int(h * rng.uniform(0.3, 1.0))
        y0 = int(rng.integers(0, max(1, h - length)))
        col = int(255 * alpha)
        cv2.line(mask, (x, y0), (x, y0 + length), col, thickness)
    return mask


def apply_look(frame: np.ndarray, look: Look, rng: np.random.Generator) -> np.ndarray:
    if (look.saturation == 1.0 and look.contrast == 1.0 and look.lift == 0.0
            and look.vignette == 0.0 and look.grain == 0.0
            and look.scratches == 0.0 and look.flicker == 0.0
            and look.glow == 0.0):
        return frame

    grey = None
    if look.saturation != 1.0 or look.grain > 0.0:
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if look.glow > 0.0:
        frame = _glow(frame, look.glow)

    if look.saturation != 1.0:
        g3 = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)
        frame = cv2.addWeighted(frame, look.saturation, g3, 1.0 - look.saturation, 0.0)

    if look.contrast != 1.0 or look.lift != 0.0:
        frame = cv2.LUT(frame, _tone_lut(look.contrast, look.lift))

    if look.flicker > 0.0:
        # A gentle, clamped random brightness wobble -- projector-bulb
        # instability. `flicker` at preset strength (0.12-0.18) should
        # read as clearly present but not distracting -- roughly a
        # 3-8% swing, clipped so it can never crush or blow out a frame.
        f = 1.0 + rng.normal(0, look.flicker * 0.35)
        f = float(np.clip(f, 1.0 - look.flicker * 0.9, 1.0 + look.flicker * 0.9))
        frame = cv2.convertScaleAbs(frame, alpha=f, beta=0)

    if look.vignette > 0.0:
        h, w = frame.shape[:2]
        frame = cv2.multiply(frame, _vignette(w, h, look.vignette), scale=1 / 255.0)

    if look.scratches > 0.0:
        h, w = frame.shape[:2]
        mask = _scratches(w, h, rng, look.scratches)
        frame = cv2.subtract(frame, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))

    if look.grain > 0.0:
        h, w = frame.shape[:2]
        weight = cv2.LUT(grey, _MID).astype(np.float32) * (1.0 / 255.0)
        n = _grain(w, h, rng) * weight * (look.grain * 11.5)
        frame = cv2.add(frame, cv2.cvtColor(n, cv2.COLOR_GRAY2BGR),
                        dtype=cv2.CV_8U)

    return frame


# --------------------------------------------------------------------------
# Captions
# --------------------------------------------------------------------------

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def load_font(size: int, override: str | None = None) -> ImageFont.FreeTypeFont:
    paths = ([override] if override else []) + FONT_CANDIDATES
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


# Text wider than this fraction of the frame wraps to the next line.
# Whisper hands us up to twelve words at a time; at 4.2% of frame height
# that is roughly twice the width of a 1080-wide vertical frame, and
# unwrapped text does not clip -- it centres and runs off BOTH edges.
CAPTION_MAX_WIDTH = 0.84
CAPTION_MAX_LINES = 3        # past this we shrink the type instead of stacking
CAPTION_LINE_SPACING = 1.22


def wrap_to_width(d: ImageDraw.ImageDraw, text: str, font, max_px: float
                  ) -> list[str]:
    """Greedy word wrap. Any newline you typed yourself is kept."""
    lines: list[str] = []
    for para in text.splitlines():
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for word in words[1:]:
            trial = f"{cur} {word}"
            if d.textlength(trial, font=font) <= max_px:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [text]


def fit_caption(d: ImageDraw.ImageDraw, text: str, size: int,
                font_override: str | None, max_px: float):
    """Wrap first; shrink only if wrapping alone is not enough.

    Shrinking is the fallback because a smaller caption is a caption you
    can still read -- three stacked lines over a face is not.
    """
    for _ in range(12):
        font = load_font(size, font_override)
        lines = wrap_to_width(d, text, font, max_px)
        widest = max(d.textlength(ln, font=font) for ln in lines)
        if len(lines) <= CAPTION_MAX_LINES and widest <= max_px:
            return font, lines
        size = int(size * 0.9)
        if size < 12:
            break
    font = load_font(max(12, size), font_override)
    return font, wrap_to_width(d, text, font, max_px)


def line_height(font) -> int:
    try:
        asc, desc = font.getmetrics()
        return asc + desc
    except Exception:
        return int(getattr(font, "size", 24) * 1.2)


def caption_alpha(cap: Caption, t: float) -> float:
    """Fade in, hold, fade out. Never a hard pop."""
    if t < cap.at or t > cap.at + cap.dur:
        return 0.0
    into = t - cap.at
    left = cap.at + cap.dur - t
    f = max(cap.fade, 1e-3)
    return float(min(1.0, into / f, left / f))


def draw_captions(frame: np.ndarray, shot: Shot, t: float,
                  font_override: str | None) -> np.ndarray:
    active = [(c, caption_alpha(c, t)) for c in shot.captions]
    active = [(c, a) for c, a in active if a > 0.001]
    if not active:
        return frame

    h, w = frame.shape[:2]
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    for cap, alpha in active:
        size = max(12, int(h * 0.042 * cap.size))
        margin = w * (1.0 - CAPTION_MAX_WIDTH) / 2
        font, lines = fit_caption(d, cap.text, size, font_override,
                                  w * CAPTION_MAX_WIDTH)

        lh = line_height(font)
        step = int(lh * CAPTION_LINE_SPACING)
        block_h = step * (len(lines) - 1) + lh

        # y0 is the TOP of the whole block, so a caption that wrapped to
        # three lines still ends where a one-line caption would.
        left_aligned = cap.pos == "lower_third"
        if cap.pos == "top":
            y0 = h * 0.08
        elif cap.pos == "center":
            y0 = (h - block_h) / 2
        elif left_aligned:
            y0 = h * 0.72
        else:                                   # bottom
            y0 = h - h * 0.10 - block_h

        a = int(255 * alpha)
        for i, line in enumerate(lines):
            lw = d.textlength(line, font=font)
            x = margin if left_aligned else (w - lw) / 2
            y = y0 + i * step
            # A soft shadow so text survives a bright background.
            d.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, int(a * 0.55)))
            d.text((x, y), line, font=font, fill=(255, 255, 255, a))

    rgba = np.array(layer)
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3][..., ::-1].astype(np.float32)     # RGB -> BGR
    out = frame.astype(np.float32) * (1 - a) + rgb * a
    return np.clip(out, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# ffmpeg plumbing
# --------------------------------------------------------------------------


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


def open_encoder(out: Path, w: int, h: int, fps: int, q: Quality,
                 audio: Path | None, audio_offset: float):
    """Video only. Sound is added afterwards by audio.build_soundtrack --
    doing it in one pass meant `-shortest` could cut the picture short
    whenever the audio ran out first, which is the common case."""
    args = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    args += ["-c:v", "libx264", "-preset", q.preset, "-crf", str(q.crf),
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    out.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(args, stdin=subprocess.PIPE)


# --------------------------------------------------------------------------
# The main loop
# --------------------------------------------------------------------------


def render(film: Film, out: Path, quality: Quality, seed: int = 0,
           font: str | None = None, quiet: bool = False) -> Path:
    fps = quality.fps or film.fps
    if quality.height:
        oh = quality.height - (quality.height % 2)
        ow = int(round(oh * film.width / film.height))
        ow -= ow % 2
    else:
        ow, oh = film.width, film.height

    ss = quality.supersample
    rw, rh = ow * ss, oh * ss
    rng = np.random.default_rng(seed)

    audio = film.resolve(film.audio) if film.audio else None
    if audio is not None and not audio.exists():
        raise SystemExit(f"Audio file not found: {audio}")

    needs_sound = bool(film.audio or film.music) or any(
        sh.kind == "video" for sh in film.shots) and film.keep_clip_audio
    video_target = out.with_name(out.stem + "__silent.mp4") if needs_sound else out
    proc = open_encoder(video_target, ow, oh, fps, quality, audio,
                        film.audio_offset)
    total = sum(max(1, int(round(s.duration * fps))) for s in film.shots)
    done = 0
    stopped_early = False

    # The outgoing shot of a dissolve, kept open one shot longer than it
    # otherwise would be. The frames it lends are the ones just past its
    # own out point -- which, at a join where a pause was cut, is exactly
    # the silence we removed. The material is already there.
    prev_shot: Shot | None = None
    prev_src = None

    try:
        for shot in film.shots:
            if stopped_early:
                break
            n = max(1, int(round(shot.duration * fps)))
            max_scale = max(window_at(shot, 0, seed).scale,
                            window_at(shot, 1, seed).scale) * 1.05
            src = open_source(film, shot, rw, rh, max_scale)

            fade_n = 0
            if shot.dissolve > 0 and prev_src is not None:
                fade_n = min(n, int(round(shot.dissolve * fps)))

            # A still shot with a still camera produces the identical warp
            # every frame. Memoising it turns a 5-second hold from 480
            # warps into 1.
            #
            # Only ever a STILL. A clip advances whether the camera moves
            # or not, and the cursor cannot stand in for that: it was read
            # BEFORE the fetch and stored AFTER it, so on the second frame
            # the pre-fetch cursor matched the stored one, the fetch was
            # skipped, and the cursor then never moved again. The clip
            # froze on its first frame for the whole shot -- with the
            # grain and the scratches still animating over the top, which
            # makes it look like a broken filter rather than a stopped
            # picture. Invisible until `static` became the right move for
            # a talking head, because it is the only move whose window
            # does not change.
            memoise = should_memoise(shot)
            memo_key = None
            memo_val = None

            for i in range(n):
                # Sub-frame accumulation = shutter. 180 degrees = half a frame.
                # Blur only what actually moves. One sub-frame per ~1.2px
                # of travel, capped at the tier's maximum.
                sub = quality.shutter
                if sub > 1:
                    sub = int(np.clip(round(motion_px(shot, i, n, seed, rw, rh) / 1.2),
                                      1, quality.shutter))

                acc = None
                used = 0
                for k in range(sub):
                    off = (k / sub) * 0.5 if sub > 1 else 0.0
                    t = (i + off) / n
                    win = window_at(shot, t, seed)
                    key = (round(win.cx, 6), round(win.cy, 6),
                           round(win.scale, 6), round(win.roll, 6))
                    if memoise and key == memo_key:
                        f = memo_val
                        if used > 0:        # identical sub-frame: skip it
                            continue
                    else:
                        img = src.frame(t * shot.duration)
                        f = compose(img, win, rw, rh, quality.interp, film, shot)
                        memo_key, memo_val = key, f
                    acc = f.astype(np.float32) if acc is None else acc + f
                    used += 1
                frame = (acc / used).astype(np.uint8) if used > 1 else memo_val.copy()

                # Cross-dissolve from the shot before. Blended here, on the
                # warped picture, so the grade and the grain are applied
                # once to the result -- grading two layers and mixing them
                # afterwards makes the overlap visibly lighter.
                if i < fade_n:
                    dt = (i + 1) / fps
                    out_win = window_past_end(prev_shot, dt, seed)
                    out_img = prev_src.frame(prev_shot.duration + dt)
                    out_frame = compose(out_img, out_win, rw, rh,
                                       quality.interp, film, prev_shot)
                    a = (i + 1) / (fade_n + 1)
                    frame = cv2.addWeighted(out_frame, 1.0 - a, frame, a, 0.0)

                if ss > 1:
                    frame = cv2.resize(frame, (ow, oh), interpolation=cv2.INTER_AREA)

                frame = apply_look(frame, film.look, rng)
                frame = draw_captions(frame, shot, i / fps, font)

                try:
                    proc.stdin.write(frame.tobytes())
                except BrokenPipeError:
                    # ffmpeg closed stdin on its own -- almost always
                    # because `-shortest` cut the output at the audio
                    # track's length, which is shorter than the video we
                    # are generating. Not a crash: what's written so far
                    # is a valid file.
                    stopped_early = True
                    break
                done += 1
                if not quiet and done % 8 == 0:
                    pct = 100 * done / total
                    sys.stderr.write(f"\r  {quality.name}  {pct:5.1f}%  "
                                     f"[{shot.id}] ")
                    sys.stderr.flush()

            # Now the dissolve is over, the outgoing shot can go.
            if prev_src is not None:
                prev_src.close()
            prev_shot, prev_src = shot, src
    finally:
        if prev_src is not None:
            prev_src.close()
        if proc.stdin and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
        proc.wait()

    if not quiet:
        sys.stderr.write(f"\r  {quality.name}  100.0%{' ' * 24}\n")
        if stopped_early and film.audio:
            sys.stderr.write(
                "  note: the voiceover is shorter than the video, so the "
                "clip was cut to match the audio. Lengthen the last shot(s), "
                "or trim media to the voiceover's length, if that's not "
                "what you want.\n")
    if proc.returncode not in (0, None) and not stopped_early:
        raise SystemExit("ffmpeg failed while encoding.")

    if needs_sound:
        from .audio import build_soundtrack
        try:
            build_soundtrack(film, video_target, out, quiet=quiet)
        finally:
            video_target.unlink(missing_ok=True)
    return out
