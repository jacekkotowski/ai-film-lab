"""
A film that says the same thing twice says so.

Found 2026-09-21, twice in one film, and the second one was published.

  1. `init` put take 1 in as the intro and the WHOLE of take 2 in as the
     closing. Take 2 re-reads the four intro sentences, so the film said
     them at 0:02 and again at 2:20. Caught by reading film.yaml;
     165.4s -> 144.8s once the closing was trimmed to the closing.

  2. `s06` shows -- and SAYS -- "Participation -> changed attitudes and
     behavior -> escalation." at 1:40 and again at 1:44. Measured in the
     narration: two real speech blocks, 101.65-106.11 and 106.62-109.21,
     both inside the shot. Nobody noticed. It is in the uploaded film,
     and in upload.txt, so it is in the YouTube chapters too.

`fit-to-length` exists as a skill for cutting what a film says twice.
Nothing ever LOOKED. The captions are already the film's own record of
what is said, so the check is a dictionary.

A repeat is only worth saying when the line is long enough to be a real
one. Short lines legitimately recur -- a refrain, a title, a two-word
answer -- and flagging those would train you to ignore this.
"""

from ffilm.checks import repeated_captions
from ffilm.spec import Caption, Film, Shot


def repeats(film) -> list[str]:
    """The named repeats only. The closing advice is prose, not a repeat."""
    return [n for n in repeated_captions(film) if not n.startswith(" ")]


def shot(sid, dur, *caps) -> Shot:
    return Shot(src="media/a.mp4", duration=dur, id=sid,
                captions=[Caption(text=t, at=a, dur=1.5, pos="lower_third")
                          for t, a in caps])


LINE = "Participation → changed attitudes and behavior → escalation."


# --------------------------------------------------------------------------
# The one that got published
# --------------------------------------------------------------------------

def test_the_same_line_twice_in_one_shot_is_named():
    f = Film(shots=[shot("s06", 6.9, (LINE, 1.94), (LINE, 5.49))])
    notes = repeats(f)
    assert len(notes) == 1
    assert LINE in notes[0]
    assert notes[0].count("s06") == 2


def test_it_says_where_both_of_them_are():
    f = Film(shots=[shot("s05", 100.0, ("something else", 0.0)),
                    shot("s06", 6.9, (LINE, 1.94), (LINE, 5.49))])
    note = repeats(f)[0]
    assert "01:41" in note and "01:45" in note


# --------------------------------------------------------------------------
# The one that was caught in time: an intro said again in the closing
# --------------------------------------------------------------------------

def test_a_line_repeated_in_a_later_shot_is_named():
    intro = "Coalition creates the capacity for violence."
    f = Film(shots=[shot("s01", 16.7, (intro, 0.0)),
                    shot("s08", 7.8, (intro, 0.0))])
    notes = repeats(f)
    assert len(notes) == 1
    assert "s01" in notes[0] and "s08" in notes[0]


def test_all_four_repeated_sentences_are_named():
    lines = ["Coalition creates the capacity for violence.",
             "Conflict can be repaired through reconciliation.",
             "Participation can turn violence into escalation.",
             "And identity and moral commitment can lead people to resist."]
    f = Film(shots=[shot("s01", 20.0, *[(t, i * 3.0) for i, t in enumerate(lines)]),
                    shot("s08", 20.0, *[(t, i * 3.0) for i, t in enumerate(lines)])])
    assert len(repeats(f)) == 4


def test_three_times_is_still_one_note_naming_three_places():
    f = Film(shots=[shot("s01", 9.0, (LINE, 0.0), (LINE, 3.0), (LINE, 6.0))])
    notes = repeats(f)
    assert len(notes) == 1
    assert notes[0].count("s01") == 3


# --------------------------------------------------------------------------
# Quiet where it should be
# --------------------------------------------------------------------------

def test_a_film_that_repeats_nothing_says_nothing():
    f = Film(shots=[shot("s01", 10.0, ("one thing said once", 0.0)),
                    shot("s02", 10.0, ("a different thing entirely", 0.0))])
    assert repeats(f) == []


def test_a_short_line_may_recur_without_comment():
    """A refrain, a title, a two-word answer."""
    f = Film(shots=[shot("s01", 10.0, ("Together,", 0.0)),
                    shot("s02", 10.0, ("Together,", 0.0))])
    assert repeats(f) == []


def test_punctuation_and_case_do_not_hide_a_repeat():
    f = Film(shots=[shot("s01", 10.0, ("We still need places and tools", 0.0)),
                    shot("s02", 10.0, ("we  still need  places and tools", 0.0))])
    assert len(repeats(f)) == 1


def test_a_film_with_no_captions_says_nothing():
    assert repeats(Film(shots=[shot("s01", 3.0)])) == []
