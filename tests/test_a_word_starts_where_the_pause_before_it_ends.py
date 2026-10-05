"""
A word starts where the pause before it ends.

Whisper often puts a word's start in the silence before it, or on the
last sound of the word before. Measured on SUMIFS SUMPRODUCT vs DAX
(2026-10-05): "Choose" at 98.61 s, but the speech pauses 98.75-99.05
and the word comes after; "The same in DAX" at 131.06 s, in a pause
that ends 131.70. The caption came up, and its highlight moved on,
before the word was said.

So a word whose start is inside a pause of 0.2 s or more, or up to
0.25 s before one, and whose end is after it, starts where the pause
ends. A word that ends before the pause is left alone: it was said
before it.
"""

from types import SimpleNamespace as W

from pytest import approx

from ffilm.voice import snap_to_pauses

PAUSES = [(98.75, 99.05), (130.06, 131.70)]


def test_a_word_said_after_the_pause_starts_when_the_pause_ends():
    words = [W(word=" slicers.", start=97.84, end=98.55),
             W(word=" Choose", start=98.61, end=99.40),
             W(word=" Table", start=99.96, end=100.30)]
    out = snap_to_pauses(words, PAUSES)
    assert [w.start for w in out] == approx([97.84, 99.05, 99.96])


def test_a_word_that_starts_inside_the_pause_moves_to_its_end():
    words = [W(word=" The", start=131.06, end=131.90),
             W(word=" same", start=131.95, end=132.20)]
    assert snap_to_pauses(words, PAUSES)[0].start == approx(131.70)


def test_a_word_said_before_the_pause_stays():
    words = [W(word=" and", start=98.55, end=98.74),
             W(word=" Choose", start=99.10, end=99.40)]
    assert [w.start for w in snap_to_pauses(words, PAUSES)] == \
        approx([98.55, 99.10])


def test_a_word_more_than_a_quarter_second_before_the_pause_stays():
    words = [W(word=" Choose", start=98.40, end=99.40)]
    assert snap_to_pauses(words, PAUSES)[0].start == approx(98.40)


def test_a_word_never_moves_onto_or_past_the_next_one():
    words = [W(word=" Choose", start=98.61, end=99.40),
             W(word=" Table", start=99.00, end=99.50)]
    assert snap_to_pauses(words, PAUSES)[0].start == approx(98.61)


def test_the_words_given_are_not_changed():
    w = W(word=" Choose", start=98.61, end=99.40)
    snap_to_pauses([w], PAUSES)
    assert w.start == 98.61
