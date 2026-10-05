"""
A film that says the same thing in other words says so.

The exact-repeat check (test_a_film_that_says_the_same_thing_twice_says_so)
only matches the same words. On SUMIFS SUMPRODUCT vs DAX (2026-10-05) the
closing take re-said the intro in other words:

    intro    SUMIFS adds by condition. / SUMPRODUCT multiplies, then adds.
             / A measure does both under every slicer.
    closing  SUMIFS adds one column by condition. / SUMPRODUCT multiplies
             first but ignores slicers. / A measure computes inside every
             filter.

Claude found that by reading; nothing in the code could. Cut, the film
went 177.8 s -> 168.0 s.

Measured before choosing the rule, on every film in projects/:
one sentence against one sentence does not separate a paraphrase from
chance (both score 0.67 shared content words). Three consecutive
captions against three do: the SUMIFS intro/closing scored 0.78 with 7
shared words; the highest unrelated passage there scored 0.50; across
20 films, only 3 other passages reached 0.6 with 5+ shared words, and
the one read (Frankfurt School) is a real restatement of the question.
"""

from ffilm.checks import paraphrased_captions
from ffilm.spec import Caption, Film, Shot


def shot(sid, dur, *texts) -> Shot:
    return Shot(src="media/a.mp4", duration=dur, id=sid,
                captions=[Caption(text=t, at=i * 2.0, dur=1.5)
                          for i, t in enumerate(texts)])


INTRO = ("SUMIFS adds by condition.",
         "SUMPRODUCT multiplies, then adds.",
         "A measure does both under every slicer.")
CLOSING = ("SUMIFS adds one column by condition.",
           "SUMPRODUCT multiplies first but ignores slicers.",
           "A measure computes inside every filter.")


def named(film):
    return [n for n in paraphrased_captions(film) if not n.startswith(" ")]


def test_a_closing_that_resays_the_intro_in_other_words_is_named():
    f = Film(shots=[shot("s01", 15.0, *INTRO),
                    shot("s02", 20.0, "Something about tables.",
                         "Rows and columns again.", "A third line here."),
                    shot("s08", 20.0, *CLOSING)])
    notes = named(f)
    assert len(notes) == 1
    assert "s01" in notes[0] and "s08" in notes[0]
    assert "00:00.00" in notes[0] and "00:35.00" in notes[0]


def test_passages_that_share_a_few_words_by_chance_are_not():
    # SUMIFS, s03 vs s06: price, revenue, divide shared -- 0.50, not a repeat
    f = Film(shots=[
        shot("s03", 20.0, "Divide by the units sold for the weighted price,",
             "157.55.", "A plain average of the prices says 170."),
        shot("s06", 20.0, "The average price divides revenue by quantity.",
             "With region in Rows,", "the total matches the formulas:")])
    assert named(f) == []


def test_one_shot_against_itself_is_not_compared():
    f = Film(shots=[shot("s01", 30.0, *INTRO, *CLOSING)])
    assert named(f) == []


def test_two_shots_are_named_once_not_once_per_overlapping_window():
    f = Film(shots=[shot("s01", 15.0, *INTRO, "Today: tables."),
                    shot("s08", 20.0, *CLOSING, "Next: ranges.")])
    assert len(named(f)) == 1
