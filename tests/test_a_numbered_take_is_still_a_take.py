"""
A take you numbered by hand is still a take.

Putting a number in front of a filename is the one way anybody has of
saying "play this one here" -- `_hint` strips the number and reads the
rest, and `place_takes` leaves a numbered take exactly where you put it.

Found 2026-09-20: `is_recording` did not strip it. It is a bare
`startswith("rec_")`, and four separate things ask it whether a file
came out of `film record`:

    scaffold._speed_for   1.2x, because people talk slower than they think
    render._sharpen       a face recorded on a webcam wants sharpening
    spec.bokeh_for        the room behind you is blurred on YOUR takes
    guide.so_far          "opening talk (14:00)" on the guide screen

So renaming `rec_20260920-1400.mp4` to `0_rec_20260920-1400.mp4` -- the
only advice there was for getting an intro to the front of a film --
moved it to the front and silently dropped its speed to 1.0, its
sharpening and its bokeh. The film changed in three ways nobody asked
for, and nothing on screen said so.
"""

from ffilm.kinds import is_recording
from ffilm.record import REC_SPEED
from ffilm.scaffold import _hint, _speed_for


def test_a_number_in_front_does_not_stop_it_being_a_take():
    assert is_recording("rec_20260920-1400")
    assert is_recording("0_rec_20260920-1400")
    assert is_recording("00_rec_20260920-1400")
    assert is_recording("7-rec_20260920-1400")


def test_a_numbered_take_keeps_the_speed_it_would_have_had():
    assert _speed_for("0_rec_20260920-1400.mp4") == REC_SPEED
    assert _speed_for("rec_20260920-1400.mp4") == REC_SPEED


def test_the_number_is_still_read_as_the_order_you_asked_for():
    role, num, clean = _hint("0_rec_20260920-1400")
    assert num == 0
    assert clean == "rec_20260920-1400"


def test_nothing_else_becomes_a_take_by_being_numbered():
    assert not is_recording("0_holiday")
    assert not is_recording("voiceover_20260917-104512")
    assert not is_recording("1_xray")
