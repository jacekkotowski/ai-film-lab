"""
A pause of exactly 0.6 s is shortened, like every longer one.

Pauses are measured in 50 ms windows, so a 0.6 s pause is 12 windows,
and its start and end are window counts times 0.05. In floating point
198.70 - 198.10 came out 0.5999999999999943, under the limit, and the
pause was left whole (SUMIFS SUMPRODUCT vs DAX, 2026-10-05: the only
pause of 0.6 s or more that survived `film tighten`).
"""

from ffilm.ingest import LEVEL_WINDOW
from ffilm.tighten import OVER, cuts_for


def test_a_twelve_window_pause_late_in_the_take_is_cut():
    s, e = 3962 * LEVEL_WINDOW, 3974 * LEVEL_WINDOW     # 198.10-198.70
    assert e - s < OVER                                  # the float trap
    assert len(cuts_for([(s, e)], [(196.0, 221.4)])) == 1


def test_a_pause_one_window_shorter_is_still_left_alone():
    s, e = 3962 * LEVEL_WINDOW, 3973 * LEVEL_WINDOW     # 0.55 s
    assert cuts_for([(s, e)], [(196.0, 221.4)]) == []
