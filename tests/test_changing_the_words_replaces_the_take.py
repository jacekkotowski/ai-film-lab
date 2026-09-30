"""Changing the words replaces the take.

Jacek, 2026-09-30: "If I press I want to change the text it automatically
means I want to retake the recording." Until then "Change the words" kept
the take, every kept camera take became a shot, and GAM Curves' first
draft (1e9d354) had three intros in it.
"""
from ffilm.booth import the_next_take_replaces_this_one


def test_changing_the_words_replaces_the_take():
    assert the_next_take_replaces_this_one("words")


def test_fluffed_it_still_replaces_the_take():
    assert the_next_take_replaces_this_one("again")


def test_record_another_still_keeps_it():
    assert not the_next_take_replaces_this_one("another")
