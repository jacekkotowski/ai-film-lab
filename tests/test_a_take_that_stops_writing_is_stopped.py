"""
A take that stops writing is stopped, and if it will not stop, killed.

Found 2026-10-02 (docs/OPEN.md): the Windows audio engine crashed during
an intro take, ffmpeg's microphone input hung, and ffmpeg never read the
`q` that SPACE sends. The window stays on "RECORDING" until ffmpeg
exits, so nothing on screen could end the take.

Measured 2026-10-05 on this laptop: a normal file grows at least every
1.43 s (voice .wav; 0.58 s camera .mp4), and ffmpeg exits 0.14-0.66 s
after `q`.
"""

from ffilm.booth import STALL_SECONDS, STOP_GRACE_SECONDS, watchdog


def test_a_take_that_is_still_growing_is_left_alone():
    assert watchdog(now=100.0, rolling=True, last_growth=99.0,
                    stopped_at=None) is None


def test_a_take_that_has_not_grown_for_the_stall_time_is_stopped():
    assert watchdog(now=100.0, rolling=True,
                    last_growth=100.0 - STALL_SECONDS - 0.1,
                    stopped_at=None) == "stop"


def test_the_camera_waking_up_is_not_a_stall():
    assert watchdog(now=100.0, rolling=False, last_growth=90.0,
                    stopped_at=None) is None


def test_a_take_still_running_after_the_grace_is_killed():
    assert watchdog(now=100.0, rolling=True, last_growth=90.0,
                    stopped_at=100.0 - STOP_GRACE_SECONDS - 0.1) == "kill"


def test_a_take_that_was_just_asked_to_stop_gets_its_grace():
    assert watchdog(now=100.0, rolling=True, last_growth=90.0,
                    stopped_at=99.0) is None


def test_the_limits_sit_well_above_what_was_measured():
    assert STALL_SECONDS >= 3 * 1.43
    assert STOP_GRACE_SECONDS >= 3 * 0.66
