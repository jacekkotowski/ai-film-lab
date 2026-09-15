"""
ENTER on "how long should it be?" keeps the whole film.

It used to mean "about 60 seconds", so a take somebody had recorded in
full came out with its pictures squeezed to a minute unless they knew to
type 0. Asked on 2026-09-15: no limit unless a number is typed.
"""

from ffilm.guide import _length_args

ARGS = ["go", "-p", "x"]


def test_enter_sets_no_limit():
    assert _length_args(ARGS, "") == ARGS


def test_zero_sets_no_limit():
    assert _length_args(ARGS, "0") == ARGS


def test_a_number_is_the_length_asked_for():
    assert _length_args(ARGS, "45") == ARGS + ["--target", "45"]
    assert _length_args(ARGS, "90,5") == ARGS + ["--target", "90.5"]


def test_something_that_is_not_a_number_sets_no_limit():
    """A typo must not quietly shorten the film either."""
    assert _length_args(ARGS, "abc") == ARGS
