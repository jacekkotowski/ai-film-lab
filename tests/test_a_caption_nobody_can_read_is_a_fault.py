"""
A caption nobody can read is a fault, not a detail.

Found 2026-09-21 on `Why there are wars`. The transcriber returned the
right WORDS for a take and junk TIMES for them:

    "Coalition creates the capacity for violence."          0.44s
    "Conflict can be repaired through reconciliation."       0.58s
    "Participation can turn violence into escalation."       0.50s
    "And identity and moral commitment can lead people to
     resist."                                                0.26s

`film caption` placed them on the spans it was handed. Nothing anywhere
said the spans were impossible, so `film check` printed OK, and the only
way Jacek found out was watching a draft and reporting "the intro has no
captions". Measured in the audio, those four sentences take 3.4-5.7s.

The rule is the one the `fix-captions` skill already carried and which
had never been code. Two clauses, because neither catches both cases:

  - the caption is on screen too briefly for the words it holds;
  - its `words:` holds fewer than half as many times as it has words,
    which is how a collapsed span looks even when its duration survives.

The duration clause is guarded by seconds-per-word on purpose. A short
line that is short because it IS short -- "Together," at 0.48s, "Light,"
at 0.51s -- is correct, measured, and must not be flagged. The skill
warned that a plain seconds-per-word rule flags a correct fast line; it
is used here only to spare the one-word lines, never on its own.
"""

from ffilm.checks import unreadable_captions
from ffilm.spec import Caption, Film, Shot


def faults(film) -> list[str]:
    """The named captions only. The closing advice is prose, not a fault."""
    return [n for n in unreadable_captions(film) if n.startswith("[")]


def film_of(*caps, dur=20.0, sid="s01") -> Film:
    return Film(shots=[Shot(src="media/a.mp4", duration=dur, id=sid,
                            captions=list(caps))])


def cap(text, dur, at=0.0, words=None) -> Caption:
    return Caption(text=text, at=at, dur=dur, pos="lower_third",
                   words=list(words) if words else [])


# --------------------------------------------------------------------------
# The four that shipped invisible
# --------------------------------------------------------------------------

def test_a_six_word_sentence_in_under_half_a_second_is_named():
    notes = faults(film_of(
        cap("Coalition creates the capacity for violence.", 0.44, words=[0.0])))
    assert len(notes) == 1
    assert "s01" in notes[0]
    assert "Coalition creates the capacity for violence." in notes[0]
    assert "0.4" in notes[0]


def test_the_worst_one_is_named_too():
    notes = faults(film_of(
        cap("And identity and moral commitment can lead people to resist.",
            0.26, words=[0.0])))
    assert len(notes) == 1
    assert "0.3" in notes[0] or "0.26" in notes[0]


def test_every_bad_caption_is_named_not_just_the_first():
    notes = faults(film_of(
        cap("Coalition creates the capacity for violence.", 0.44, words=[0.0]),
        cap("Conflict can be repaired through reconciliation.", 0.58, at=1.0,
            words=[0.0]),
        cap("Participation can turn violence into escalation.", 0.50, at=2.0,
            words=[0.0])))
    assert len(notes) == 3


# --------------------------------------------------------------------------
# A collapsed span that happens to be long enough
# --------------------------------------------------------------------------

def test_a_caption_that_heard_one_word_in_ten_is_named():
    """Two seconds is readable; one word time out of ten is not placeable."""
    notes = faults(film_of(
        cap("And identity and moral commitment can lead people to resist.",
            2.0, words=[0.0])))
    assert len(notes) == 1
    assert "1 of 10" in notes[0] or "1 word time" in notes[0]


def test_a_caption_with_all_its_word_times_is_left_alone():
    notes = faults(film_of(
        cap("Coalition creates the capacity for violence.", 2.86,
            words=[0.0, 0.6, 1.5, 1.72, 2.12, 2.47])))
    assert notes == []


# --------------------------------------------------------------------------
# Short because it IS short. These are correct and must stay quiet.
# --------------------------------------------------------------------------

def test_a_one_word_caption_of_half_a_second_is_not_a_fault():
    """"Together," measured at 0.48s on Why there are wars. Correct."""
    assert faults(film_of(cap("Together,", 0.48, words=[0.0]))) == []


def test_the_bauhaus_one_word_line_left_alone_on_purpose_stays_quiet():
    """"Light," at 0.51s, decided 2026-09-19 and deliberately kept."""
    assert faults(film_of(cap("Light,", 0.51, words=[0.0]))) == []


def test_a_short_two_word_caption_is_not_a_fault():
    assert faults(film_of(cap("food and", 0.8, words=[0.0, 0.4]))) == []


def test_an_ordinary_caption_says_nothing():
    notes = faults(film_of(
        cap("these processes show how collective violence can begin,", 3.63,
            words=[0.0, .52, .98, 1.75, 2.13, 2.47, 2.9, 3.25])))
    assert notes == []


def test_a_film_with_no_captions_says_nothing():
    assert faults(Film(shots=[Shot(src="media/a.jpg", duration=3.0,
                                                id="s01")])) == []


def test_a_caption_with_no_word_times_at_all_is_judged_on_its_length_only():
    """`words:` is optional. Its absence is not evidence of anything."""
    assert faults(film_of(
        cap("these processes show how collective violence can begin,", 3.63))) == []
    assert len(faults(film_of(
        cap("Coalition creates the capacity for violence.", 0.44)))) == 1


# --------------------------------------------------------------------------
# The false positives a 0.30 s/word threshold produced across the 19 films
# in projects/. Every one of these is a correct caption and must stay quiet.
# --------------------------------------------------------------------------

def test_fast_but_sayable_is_not_a_fault():
    """3.8 words/sec. Fast, and people talk like that."""
    assert faults(film_of(cap("That is the tradition.", 1.04))) == []
    assert faults(film_of(cap("Mother and child.", 0.78))) == []
    assert faults(film_of(cap("Blur the original,", 0.73))) == []


def test_a_caption_shortened_so_it_does_not_collide_is_not_a_fault():
    """`stop_overlap` ends a caption where the next begins. That is the
    toolkit working, and it leaves short durations everywhere."""
    assert faults(film_of(cap("I lose my backpack.", 1.18))) == []
    assert faults(film_of(cap("including Jews.", 0.53))) == []


def test_a_single_word_of_a_quarter_second_is_not_a_fault():
    assert faults(film_of(cap("Stamped.", 0.28))) == []
    assert faults(film_of(cap("Poland.", 0.26))) == []


def test_four_words_in_under_half_a_second_still_is_one():
    """8.9 words/sec. Nobody says that."""
    assert len(faults(film_of(cap("It is a risk.", 0.45)))) == 1
