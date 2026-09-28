"""
Parallax: as the camera moves, what is near slides past what is far.
The subject -- the depth at `focus` -- stays exactly where the flat
camera would have put it; nearer moves more, farther moves the other
way; and at mid-move nothing is shifted at all, so the photo is itself
halfway through the shot.

The depth here is a ramp: far on the left, near on the right, and the
subject in the middle.
"""

import numpy as np

from ffilm import render
from ffilm.moves import window_at, window_mid
from ffilm.spec import Shot

H, W, OW, OH = 120, 180, 90, 60


def ramp():
    return np.tile(np.linspace(0, 1, W, dtype=np.float32), (H, 1))


def shift(move, t, strength=0.5):
    """How far each output pixel's source point moved, in source pixels
    across, against the flat camera at the same moment."""
    shot = Shot.parse({"src": "a.jpg", "move": move, "focus": [0.5, 0.5]}, 0)
    par = render.Parallax(ramp(), 0.5, window_mid(shot), strength)
    win = window_at(shot, t)
    plain_x, _ = render.source_maps(H, W, win, OW, OH)
    moved_x, _ = render.parallax_maps(H, W, win, OW, OH, par)
    return moved_x - plain_x, plain_x


def test_the_subject_does_not_shift():
    dx, x = shift("pan_right", 1.0)
    at_subject = np.abs(x - W * 0.5) < 1.0
    assert at_subject.any()
    assert np.abs(dx[at_subject]).max() < 0.05


def test_nearer_shifts_more_and_farther_the_other_way():
    dx, x = shift("pan_right", 1.0)
    row = dx[OH // 2]
    near, far = row[-5:].mean(), row[:5].mean()
    assert near > 0 > far                 # opposite ways
    assert row[-1] > row[OW * 3 // 4] > 0  # nearer moves more


def test_the_camera_going_back_turns_it_round():
    start, _ = shift("pan_right", 0.0)
    end, _ = shift("pan_right", 1.0)
    assert start[OH // 2, -1] < 0 < end[OH // 2, -1]


def test_at_mid_move_nothing_is_shifted():
    shot = Shot.parse({"src": "a.jpg", "move": "pan_right"}, 0)
    mid = window_mid(shot)
    par = render.Parallax(ramp(), 0.5, mid, 0.5)
    plain = render.source_maps(H, W, mid, OW, OH)
    moved = render.parallax_maps(H, W, mid, OW, OH, par)
    assert np.allclose(plain[0], moved[0]) and np.allclose(plain[1], moved[1])


def test_stronger_is_more():
    weak, _ = shift("pan_right", 1.0, 0.3)
    strong, _ = shift("pan_right", 1.0, 0.8)
    assert abs(strong[OH // 2, -1]) > abs(weak[OH // 2, -1])


def test_a_push_in_brings_the_near_side_closer_than_the_far():
    """A zoom has no travel sideways to speak of; there the near things
    grow a little more than the far ones instead."""
    dx, x = shift("push_in", 1.0)
    row = dx[OH // 2]
    centre = OW // 2
    # Near side (right, past centre) is pulled towards the centre of the
    # window: sampled from closer in, so it looks bigger.
    assert row[-1] < 0
    assert np.isfinite(row).all()
