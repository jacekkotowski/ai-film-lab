"""
A two-column slide shows each column in turn.

Asked for 2026-10-01: a vertical Short over horizontal slides of two
columns (PNG 2160x1920, each column the frame's own shape). The camera
holds on the left column, pans gently across exactly mid-shot, and holds
on the right one. While it travels it opens out a little and closes in
again, so the pan breathes instead of sliding.
"""

from ffilm.moves import COLUMNS_HOLD, window_at
from ffilm.render import window_affine
from ffilm.spec import Shot


def _slide(**extra):
    return Shot.parse({"src": "media/excel.png", "move": "columns",
                       "duration": 12.0, **extra}, 0)


def test_the_camera_holds_still_on_the_left_column_then_on_the_right():
    s = _slide()
    for t in (0.0, COLUMNS_HOLD / 2, COLUMNS_HOLD):
        assert window_at(s, t) == window_at(s, 0.0)
        assert window_at(s, 1.0 - t) == window_at(s, 1.0)
    assert abs(window_at(s, 0.0).cx - 0.25) < 1e-9
    assert abs(window_at(s, 1.0).cx - 0.75) < 1e-9


def test_the_pan_is_exactly_mid_shot():
    s = _slide()
    assert abs(window_at(s, 0.5).cx - 0.5) < 1e-9


def test_the_pan_opens_out_a_little_and_closes_in_again():
    s = _slide()
    held, mid = window_at(s, 0.0).scale, window_at(s, 0.5).scale
    assert mid < held
    assert window_at(s, 1.0).scale == held
    assert held - mid <= 0.06                  # delicate, not a zoom


def test_each_held_column_is_inside_its_own_half_of_the_slide():
    # A 2160x1920 slide in a 1080x1920 frame, cropped as usual.
    s = _slide()
    for t, lo, hi in ((0.0, 0, 1080), (1.0, 1080, 2160)):
        _, cx, _, w = window_affine(1920, 2160, window_at(s, t), 1080, 1920)
        assert lo <= cx - w / 2 and cx + w / 2 <= hi


def test_the_widest_moment_never_shows_past_the_top_or_bottom():
    s = _slide()
    for i in range(101):
        assert window_at(s, i / 100).scale >= 1.0


def test_every_other_move_is_untouched():
    p = Shot.parse({"src": "media/photo.jpg", "move": "push_in",
                    "duration": 5.0}, 0)
    assert window_at(p, 0.3) != window_at(p, 0.0)  # still moves from frame 1
