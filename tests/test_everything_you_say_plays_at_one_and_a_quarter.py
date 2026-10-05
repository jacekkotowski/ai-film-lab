"""
Everything you say -- a take to the camera, the narration over pictures --
plays at 1.25 in a new film.

Jacek heard SUMIFS SUMPRODUCT vs DAX fitted from 1.2 to 1.25 (2026-10-05)
and asked for 1.25 always. Measured on that film: 107 wpm at 1.2, 112 at
1.25; atempo round-trip distortion 6.5 dB at 1.2, 6.6 dB at 1.25, no knee
until past 1.35 (docs/tech/audio.md). One number for both kinds of voice,
as decision 0010 requires.
"""

from ffilm.record import MAX_SPEED, REC_SPEED
from ffilm.scaffold import _speed_for


def test_a_take_and_the_narration_both_play_at_one_and_a_quarter():
    assert _speed_for("media/rec_20261005-103738.mp4") == 1.25
    assert _speed_for("media/close_rec_20261005-105330.mp4") == 1.25
    assert _speed_for("media/voiceover_20261005-105141.wav") == 1.25


def test_fit_is_never_asked_to_go_below_the_default():
    assert MAX_SPEED >= REC_SPEED
