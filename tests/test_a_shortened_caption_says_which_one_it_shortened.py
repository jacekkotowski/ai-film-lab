"""
When a caption is shortened, the note names the caption it shortened.

`stop_overlap` ends a caption exactly where the next one begins, so the
two never sit on screen at once. That is correct and routine. The note
it printed read:

    [s04] shortened to 2.20s, the next caption starts: "They created a
    physical fix."

but the text at the end is the caption that WAS shortened, not the one
that starts. Found 2026-09-20 on 1930s Austria Had Photoshop: Jacek read
it as a complaint about the shot it names, went looking for a fault in a
recording that was entirely correct, and the line under it -- "that shot
may be too short for what is said over it" -- agreed with him.

Two adjacent captions two seconds apart is ordinary speech, not a short
shot, so the note now says what happened and nothing more.
"""

from ffilm.caption_fit import stop_overlap
from ffilm.spec import Caption


def notes(caps):
    warnings = []
    stop_overlap(caps, "s04", warnings)
    return warnings


def test_the_note_names_the_caption_that_was_shortened():
    caps = [Caption(text="They created a physical fix.", at=0.0, dur=4.5,
                    pos="lower_third"),
            Caption(text="A positive copy was exposed", at=2.2, dur=3.0,
                    pos="lower_third")]
    w = notes(caps)
    assert len(w) == 1
    assert "They created a physical fix." in w[0]
    assert "A positive copy" not in w[0]
    assert "2.20s" in w[0]


def test_the_note_does_not_read_as_a_complaint_about_the_next_caption():
    caps = [Caption(text="first", at=0.0, dur=4.5, pos="lower_third"),
            Caption(text="second", at=2.2, dur=3.0, pos="lower_third")]
    assert "the next caption starts:" not in notes(caps)[0]


def test_captions_that_do_not_collide_say_nothing():
    caps = [Caption(text="first", at=0.0, dur=2.0, pos="lower_third"),
            Caption(text="second", at=2.2, dur=3.0, pos="lower_third")]
    assert notes(caps) == []


def test_the_caption_really_is_shortened_not_dropped():
    caps = [Caption(text="first", at=0.0, dur=4.5, pos="lower_third"),
            Caption(text="second", at=2.2, dur=3.0, pos="lower_third")]
    out = stop_overlap(caps, "s04", [])
    assert [c.text for c in out] == ["first", "second"]
    assert out[0].dur == 2.2
