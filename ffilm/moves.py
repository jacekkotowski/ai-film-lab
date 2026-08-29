"""
moves.py  --  the movement vocabulary.

This is the file that decides whether the output looks like cinema or like
a school slideshow. Two ideas do most of the work:

1. EASING. A camera that starts and stops abruptly reads as a machine.
   Real camera moves accelerate and decelerate. Linear interpolation is
   the single most common reason Ken Burns looks cheap.

2. NEVER COMPLETING THE MOVE. We cut while the camera is still travelling.
   A move that visibly finishes and then holds is a slideshow. The
   `settle` parameter below controls how much of the move we actually
   show -- 0.85 means we stop 15% short, so it still feels alive at the cut.

Everything here is deliberately small and tweakable. If a move feels wrong,
the fix is almost always a number in this file, not new code.
"""

from __future__ import annotations

import math
import random

from .spec import Shot, Window

# --------------------------------------------------------------------------
# Easing curves.  Each maps t in [0,1] -> eased t in [0,1].
# --------------------------------------------------------------------------


def _linear(t: float) -> float:
    return t


def _sine_in_out(t: float) -> float:
    """The workhorse. Gentle start, gentle stop. Use this by default."""
    return 0.5 * (1.0 - math.cos(math.pi * t))


def _quad_out(t: float) -> float:
    """Fast start, slow settle. Good for a reveal."""
    return 1.0 - (1.0 - t) ** 2


def _quad_in(t: float) -> float:
    """Slow start, accelerating. Good just before a hard cut."""
    return t * t


def _cubic_in_out(t: float) -> float:
    """More pronounced than sine. Slightly dramatic."""
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _expo_out(t: float) -> float:
    """Very fast start, very long settle. A camera coming to rest."""
    return 1.0 if t >= 1.0 else 1.0 - 2 ** (-10 * t)


def _linear_damped(t: float) -> float:
    """Almost constant velocity, but with the corners knocked off.
    This is what a real dolly on a good head actually does."""
    k = 0.15
    if t < k:
        return (t / k) ** 2 * k * 0.5
    if t > 1 - k:
        u = (1 - t) / k
        return 1 - u**2 * k * 0.5
    return t * (1 - k) + k * 0.25


EASINGS = {
    "linear": _linear,
    "sine_in_out": _sine_in_out,
    "quad_out": _quad_out,
    "quad_in": _quad_in,
    "cubic_in_out": _cubic_in_out,
    "expo_out": _expo_out,
    "linear_damped": _linear_damped,
}


def ease(name: str, t: float) -> float:
    return EASINGS.get(name, _sine_in_out)(max(0.0, min(1.0, t)))


# --------------------------------------------------------------------------
# The vocabulary itself.
# --------------------------------------------------------------------------

# How far a "full strength" move travels. These are the taste knobs.
PUSH = 0.16      # scale change for a push in / pull out
PAN = 0.13       # fraction of frame width travelled on a pan
DRIFT = 0.045    # a barely-there move. Almost static, but not dead.
ROLL = 0.5       # degrees of roll added to lateral moves. Subtle on purpose.
SETTLE = 0.85    # show only this fraction of the move, then cut. See above.
BASE = 1.06      # never sit at scale 1.0 -- leaves room to move without
                 # hitting the edge of the image, and hides bad edges.

# A photograph is a place you move around IN. A person talking to camera
# is a subject you FRAME and then leave alone. Those want opposite
# treatment, and until now video got the photograph's:
#
# SUBJECT_LEAD -- a still honours its focus point only a third of the way
#   (mid_x below), because drifting from the middle towards the subject is
#   the move. A talking head has nowhere to drift to: you either have the
#   person centred or you have their ear out of frame. So video honours
#   the focus point in full.
#
# VIDEO_BASE -- a webcam frame has clean edges and needs no margin to hide
#   them, and a 16:9 picture cropped into a 9:16 frame is already keeping
#   only 32% of its width. Every extra percent of zoom on top of that is
#   both more of the speaker cut off and more sharpness thrown away
#   blowing 720 lines up to 1920.
SUBJECT_LEAD = 1.0
VIDEO_BASE = 1.0

MOVES = [
    "push_in", "pull_out", "pan_left", "pan_right",
    "tilt_up", "tilt_down", "drift_left", "drift_right",
    "punch_in", "reveal", "static",
]

# Moves that read as "similar" -- we avoid using two from the same family
# back to back, which is what kills the mechanical feeling.
FAMILY = {
    "push_in": "in", "punch_in": "in",
    "pull_out": "out", "reveal": "out",
    "pan_left": "lateral", "pan_right": "lateral",
    "drift_left": "lateral", "drift_right": "lateral",
    "tilt_up": "vertical", "tilt_down": "vertical",
    "static": "static",
}


def windows_for(shot: Shot, seed: int = 0) -> tuple[Window, Window]:
    """Turn a named move + focus point into a concrete start and end window.

    If the shot already has explicit `from`/`to`, we use those untouched --
    that is the escape hatch for hand-tuning a shot that matters.
    """
    if shot.frm is not None and shot.to is not None:
        return shot.frm, shot.to

    rng = random.Random(f"{shot.id}{shot.src}{seed}")
    fx, fy = shot.focus if shot.focus else (0.5, 0.5)
    a = shot.amount

    # See SUBJECT_LEAD / VIDEO_BASE above. A still is explored; a person
    # is framed.
    video = shot.kind == "video"
    base = VIDEO_BASE if video else BASE
    lead_mid = SUBJECT_LEAD if video else 0.35
    lead_near = SUBJECT_LEAD if video else 0.85

    # Start centred between the frame middle and the subject, end closer to
    # the subject. Moving TOWARDS the thing that matters is the whole trick.
    mid_x = 0.5 + (fx - 0.5) * lead_mid
    mid_y = 0.5 + (fy - 0.5) * lead_mid
    near_x = 0.5 + (fx - 0.5) * lead_near
    near_y = 0.5 + (fy - 0.5) * lead_near

    # A little randomness so twenty shots don't move in identical arcs.
    jx = rng.uniform(-0.012, 0.012)
    jy = rng.uniform(-0.012, 0.012)
    roll_dir = rng.choice([-1.0, 1.0])

    m = shot.move
    if m == "auto":
        m = "push_in"

    if m == "push_in":
        f = Window(mid_x, mid_y, base, 0.0)
        t = Window(near_x + jx, near_y + jy, base + PUSH * a, ROLL * a * roll_dir * 0.4)
    elif m == "punch_in":
        # Faster, tighter, more aggressive. For a beat you want to hit.
        f = Window(mid_x, mid_y, base + 0.04, 0.0)
        t = Window(near_x, near_y, base + PUSH * 1.7 * a, 0.0)
    elif m == "pull_out":
        f = Window(near_x, near_y, base + PUSH * a, ROLL * a * roll_dir * 0.4)
        t = Window(mid_x + jx, mid_y + jy, base, 0.0)
    elif m == "reveal":
        # Start tight on the subject, open right out. Good for an establisher.
        f = Window(fx, fy, base + PUSH * 2.0 * a, 0.0)
        t = Window(0.5, 0.5, base, 0.0)
    elif m in ("pan_left", "pan_right"):
        d = -1.0 if m == "pan_left" else 1.0
        s = base + 0.06 * a
        f = Window(mid_x - d * PAN * a * 0.5, mid_y, s, -ROLL * a * 0.5 * d)
        t = Window(mid_x + d * PAN * a * 0.5, mid_y + jy, s, ROLL * a * 0.5 * d)
    elif m in ("tilt_up", "tilt_down"):
        d = -1.0 if m == "tilt_up" else 1.0
        s = base + 0.06 * a
        f = Window(mid_x, mid_y - d * PAN * a * 0.45, s, 0.0)
        t = Window(mid_x + jx, mid_y + d * PAN * a * 0.45, s, 0.0)
    elif m in ("drift_left", "drift_right"):
        # The most useful move in the set. Reads as "not a photograph"
        # without ever announcing itself.
        d = -1.0 if m == "drift_left" else 1.0
        s = base + 0.03 * a
        f = Window(mid_x - d * DRIFT * a, mid_y, s, 0.0)
        t = Window(mid_x + d * DRIFT * a, mid_y, s + 0.012 * a, ROLL * 0.3 * a * d)
    elif m == "static":
        f = Window(mid_x, mid_y, base, 0.0)
        t = Window(mid_x, mid_y, base, 0.0)
    else:
        raise SystemExit(
            f"Unknown move {m!r} in shot {shot.id}. Known moves: {', '.join(MOVES)}"
        )

    # Apply an explicit override on just one end, if given.
    if shot.frm is not None:
        f = shot.frm
    if shot.to is not None:
        t = shot.to
    return f, t


def window_at(shot: Shot, t: float, seed: int = 0) -> Window:
    """The camera position at normalised time t within this shot."""
    f, to = windows_for(shot, seed)
    e = ease(shot.ease, t) * SETTLE
    return f.lerp(to, e)


def window_past_end(shot: Shot, dt: float, seed: int = 0) -> Window:
    """Where the camera would be `dt` seconds AFTER this shot's last frame.

    Only a dissolve needs this. While the outgoing picture fades it should
    keep travelling -- a shot that freezes the instant the next one starts
    is the thing that makes a dissolve look like a slideshow transition
    rather than two pieces of film overlapping.

    SETTLE means we normally stop short of the full move (see the note at
    the top of this file), so there is always some travel left to spend.
    """
    f, to = windows_for(shot, seed)
    over = SETTLE * (1.0 + dt / max(shot.duration, 0.1))
    return f.lerp(to, min(1.0, over))


def choose_moves(shots, seed: int = 0) -> None:
    """Assign a move to every shot marked `auto`, avoiding repetition.

    The rule that matters: never two moves from the same family in a row.
    This is what stops twenty photographs feeling like a conveyor belt.
    """
    rng = random.Random(seed)
    pool = ["push_in", "pull_out", "pan_left", "pan_right",
            "drift_left", "drift_right", "tilt_up", "push_in", "drift_right"]
    last_family = None
    for s in shots:
        if s.move != "auto":
            last_family = FAMILY.get(s.move, "static")
            continue
        options = [m for m in pool if FAMILY[m] != last_family]
        pick = rng.choice(options or pool)
        s.move = pick
        last_family = FAMILY[pick]
