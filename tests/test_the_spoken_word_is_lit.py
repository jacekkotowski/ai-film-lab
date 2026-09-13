"""
The word being said is the word that is lit.

The speech model has always known when each word starts -- voice.py asks
it for exactly that -- and then threw the times away once the words were
grouped into lines. A caption that lights each word as it is spoken is
read WITH the voice instead of ahead of it, which is most of what makes
a Short captioned this way easy to follow with the sound off.

So each caption keeps `words:` -- when each word starts, in seconds from
the caption's own start -- and the renderer lights the one being said.
Delete the `words:` line and that caption goes back to plain white.
"""

from types import SimpleNamespace as W

import yaml
from pytest import approx

from ffilm.caption_fit import _place
from ffilm.editor import dump
from ffilm.render import lit_word
from ffilm.scaffold import _caption_lines
from ffilm.spec import Caption
from ffilm.voice import Line, attach_word_starts


# --------------------------------------------------------------------------
# Which word is lit
# --------------------------------------------------------------------------

def test_the_word_whose_turn_it_is_is_lit():
    c = Caption(text="one two three", at=1.0, dur=3.0, words=[0.0, 0.5, 1.2])
    assert lit_word(c, 0.1) == 0
    assert lit_word(c, 0.7) == 1
    assert lit_word(c, 2.9) == 2


def test_nothing_is_lit_before_the_first_word_starts():
    c = Caption(text="one two", at=0.0, dur=2.0, words=[0.3, 0.8])
    assert lit_word(c, 0.1) is None


def test_a_caption_without_word_times_lights_nothing():
    assert lit_word(Caption(text="one two", dur=2.0), 1.0) is None


def test_a_caption_whose_text_was_edited_still_lights_in_step():
    """Six words heard, three left on screen after editing: halfway
    through the speech is halfway through the caption."""
    c = Caption(text="alpha beta gamma", dur=3.0,
                words=[0.0, 0.3, 0.6, 0.9, 1.2, 1.5])
    assert lit_word(c, 0.0) == 0
    assert lit_word(c, 0.95) == 1
    assert lit_word(c, 1.6) == 2


# --------------------------------------------------------------------------
# The times survive every step from the speech model to film.yaml
# --------------------------------------------------------------------------

def test_each_line_keeps_the_start_of_every_word_in_it():
    lines = [Line("hello there", 1.0, 2.0), Line("again", 3.0, 3.6)]
    words = [W(start=1.0), W(start=1.5), W(start=3.1)]
    attach_word_starts(lines, words)
    assert lines[0].words == [1.0, 1.5]
    assert lines[1].words == [3.1]


def test_a_sped_up_shot_lights_its_words_sooner():
    """Speed 1.2 plays the take 20% faster, so the word said half a second
    into the line is on screen at 0.42 s into the caption."""
    ln = Line("hello there", 6.0, 7.0, words=[6.0, 6.5])
    cap = _place("s01", 0.0, 12.0, ln, [], speed=1.2)
    assert cap.words == approx([0.0, 0.42], abs=0.01)


def test_word_times_are_written_into_film_yaml_and_read_back():
    c = Caption(text="hi there", at=1.0, dur=2.0, words=[0.0, 0.41])
    text = "\n".join(_caption_lines([c], ""))
    parsed = Caption.parse(yaml.safe_load(text)["captions"][0])
    assert parsed.words == [0.0, 0.41]


def test_the_bench_hands_word_times_back_as_it_found_them(tmp_path):
    (tmp_path / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    out = dump(tmp_path, {
        "fps": 24, "width": 1080, "height": 1920,
        "shots": [{"id": "s01", "src": "media/a.jpg", "kind": "still",
                   "duration": 5.0, "move": "static", "ease": "linear",
                   "amount": 1.0, "focus": [0.5, 0.5], "note": "",
                   "dissolve": 0.0, "fill": None, "frm": None, "to": None,
                   "captions": [{"text": "hi there", "at": 1.0, "dur": 2.0,
                                 "pos": "bottom", "words": [0.0, 0.41]}]}]})
    cap = yaml.safe_load(out)["shots"][0]["captions"][0]
    assert cap["words"] == [0.0, 0.41]
