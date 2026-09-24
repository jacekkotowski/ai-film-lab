"""
A camera take is shown at the moment it was filmed.

Found 2026-09-24 on the Frankfurt School final: the lips drifted from
0.5 s late to 0.5 s early through the intro. The webcam records at a
varying rate (1423 frames in 31.1 s, labelled 60 fps, OpenCV says 44.72),
and the renderer picked frame = time x that one number. The draft never
showed it: its proxy is re-timed to a steady rate by ffmpeg. The fix
picks the frame whose own timestamp is on screen at that time.
"""

from ffilm.render import frame_on_screen


# a take that runs at 40 fps for 1 s, then 50 fps for 1 s
VARYING = [i / 40 for i in range(40)] + [1.0 + i / 50 for i in range(50)]


def test_the_frame_shown_is_the_one_filmed_at_that_time():
    for t in (0.0, 0.26, 0.99, 1.0, 1.37, 1.98):
        i = frame_on_screen(VARYING, t)
        assert VARYING[i] <= t + 1e-9
        assert i == len(VARYING) - 1 or VARYING[i + 1] > t + 1e-9


def test_one_average_rate_would_have_been_wrong():
    # what the old code did, with the take's average rate (45 fps)
    t = 1.0
    old = round(t * 45)
    assert abs(VARYING[old] - t) > 0.1           # the fault, measured
    assert VARYING[frame_on_screen(VARYING, t)] == 1.0


def test_before_the_first_frame_is_the_first_frame():
    assert frame_on_screen([0.02, 0.05], 0.0) == 0


def test_past_the_end_is_the_last_frame():
    assert frame_on_screen(VARYING, 99.0) == len(VARYING) - 1


def test_a_steady_rate_gives_the_old_answer():
    steady = [i / 24 for i in range(240)]
    for t in (0.0, 1.5, 7.3, 9.9):
        assert frame_on_screen(steady, t) == int(t * 24 + 1e-9)
