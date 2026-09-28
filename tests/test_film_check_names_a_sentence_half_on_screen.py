"""
`film check` names a sentence that is only half on screen.

What Is Love, 2026-09-28: "In one study," and "A 2018 meta-analysis by
Kathrin Karsay," were said and never captioned, and `film check` printed
OK. It could not know: it read only the captions that were there.

The script says what should be there. A sentence with none of its
clauses on screen was cut on purpose (fit-to-length drops whole
sentences) or not recorded yet, so that is not named. A sentence with
some of its clauses on screen and some missing is never on purpose.
That is what this names.
"""

from ffilm.checks import half_captioned
from ffilm.spec import Caption, Film, Shot

SCRIPT = ("Frans de Waal documented consolation. In one study, researchers "
          "examined 3,003 fights and what happened afterwards.\n\n"
          "Empathy is far older than our species.")


def film(*texts) -> Film:
    return Film(shots=[Shot(src="media/a.png", duration=20.0, id="s06",
                            captions=[Caption(text=t, at=i * 2.0, dur=1.5,
                                              pos="lower_third")
                                      for i, t in enumerate(texts)])])


def named(notes):
    return [n for n in notes if not n.startswith(" ")]


def test_a_clause_missing_from_a_sentence_on_screen_is_named():
    f = film("Frans de Waal documented consolation.",
             "researchers examined 3,003 fights",
             "and what happened afterwards.",
             "Empathy is far older than our species.")
    notes = named(half_captioned([SCRIPT], f))
    assert len(notes) == 1
    assert '"In one study,"' in notes[0]


def test_a_sentence_cut_whole_is_not_named():
    f = film("Frans de Waal documented consolation.",
             "Empathy is far older than our species.")
    assert half_captioned([SCRIPT], f) == []


def test_a_clause_of_one_or_two_words_proves_nothing():
    """Swept over 22 films: "kitchen," and "WC," from one Bauhaus
    sentence were found inside a DIFFERENT caption, so a sentence none of
    which was on screen looked half there."""
    script = "A small but complete home, with kitchen, WC, and heating."
    f = film("a carefully designed small apartment with kitchen, bathroom,")
    assert half_captioned([script], f) == []


def test_a_sentence_broken_across_two_captions_is_whole():
    f = film("Frans de Waal documented consolation.",
             "In one study, researchers examined",
             "3,003 fights and what happened afterwards.",
             "Empathy is far older than our species.")
    assert half_captioned([SCRIPT], f) == []
