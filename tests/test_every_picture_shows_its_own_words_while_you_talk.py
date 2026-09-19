"""
Every picture shows its own words while you talk -- the words you pasted
in the window, one paragraph per picture, in the film's order.

Found 2026-09-19 on German Forgotten Bauhaus Hope: eight paragraphs
pasted into the narration window for ten pictures, and while recording
there was no text at all. The pictures were paired with the words once,
before the window opened -- with narration.txt, which was empty. What
was pasted never reached them.

Eight paragraphs for ten pictures also needs a way to say which two get
none: `-` on its own is a picture with no words, and `[5]` jumps to
picture 5 and carries on from there, 6, 7...
"""

from ffilm import scaffold
from ffilm.voice import script_paragraphs

PICS = [f"media/{i}_.jpg" for i in range(1, 6)]


def steps(text):
    return scaffold.narration_steps(PICS, script_paragraphs(text))


def test_a_dash_is_a_picture_with_no_words():
    got = steps("One.\n\n-\n\nThree.")
    assert got[:3] == [("media/1_.jpg", "One."), ("media/2_.jpg", ""),
                       ("media/3_.jpg", "Three.")]


def test_a_numbered_paragraph_jumps_there_and_the_next_carries_on():
    got = steps("One.\n\n[4] Four.\n\nFive.")
    assert got == [("media/1_.jpg", "One."), ("media/2_.jpg", ""),
                   ("media/3_.jpg", ""), ("media/4_.jpg", "Four."),
                   ("media/5_.jpg", "Five.")]


def test_the_pictures_are_always_shown_in_the_film_order():
    got = steps("[3] Three.\n\nFour.")
    assert [p for p, _ in got] == PICS


def test_the_film_puts_each_paragraph_under_the_same_picture():
    paras = script_paragraphs("One.\n\n-\n\n[4] Four.\n\nFive.")
    assert scaffold.paragraph_pictures(paras, PICS) == [
        "media/1_.jpg", "media/2_.jpg", "media/4_.jpg", "media/5_.jpg"]
