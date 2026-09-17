"""
A narration recorded separately, longer than the pictures under it.

audio.build_soundtrack's last filter is `apad,atrim=0:total` -- a
narration that runs past the end of the film is silently cut to fit,
and until now nothing said so. Measured 2026-09-17 on the scratch
project (docs/plans/2026-09-17/PLAN.md, item 1): a 14s narration under
a 27.4s film played in full, and a 41s narration under the same film
would lose its last 13.6s with no message anywhere.

Numbers only here. Nothing touches ffmpeg.
"""

from pytest import approx

from ffilm.checks import narration_note


def test_a_narration_shorter_than_the_film_says_nothing():
    assert narration_note(14.0, 27.4) is None


def test_a_narration_a_hair_longer_than_the_film_says_nothing():
    """Frame rounding, not a real overrun -- see spec.TRIM_WORTH_SAYING
    for the same reasoning applied to captions."""
    assert narration_note(27.6, 27.4) is None


def test_a_narration_that_will_lose_its_end_names_the_seconds_lost():
    said = narration_note(41.0, 27.4)
    assert "41s" in said
    assert "27.4s" in said
    assert "14s" in said         # 41 - 27.4, rounded


def test_it_suggests_the_target_to_fix_it():
    said = narration_note(41.0, 27.4)
    assert "--target 41" in said
