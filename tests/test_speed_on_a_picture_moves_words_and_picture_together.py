"""
`speed` on a picture speeds its words AND shortens the picture to match.

Until 2026-09-20 `speed:` on a slide was a dead key. `Shot.parse` left
the picture on screen for (out - in) + a breath whatever it said, and
`audio.speech_specs` passed a hard 1.0 for every slide -- so writing
`speed: 1.2` over a photograph changed nothing at all, silently.

Jacek asked for 1.2 on the narration to match the 1.2 on his talking
takes, wrote it, and got no difference. The comment in audio.py defends
a DIFFERENT rule -- holding a photograph longer must not stretch the
words, which is `duration:` and is still true below -- and `speed:` was
caught up in it.

The thing this file exists to prevent: the two halves moving apart. A
slide's picture and its words have to come out the same length at every
speed, because the narration is one continuous recording cut into
pieces, and a piece that plays short pushes every later piece out of
step with its photograph.
"""

import pytest

from ffilm import audio
from ffilm.spec import VOICE_TAIL, Film, Shot

WORDS = 25.25            # seconds of narration in this piece


def slide(speed: float, duration=None) -> Shot:
    d = {"src": "media/a.jpg", "voice": "media/v.wav",
         "in": "00:00.00", "out": "00:25.25", "speed": speed}
    if duration is not None:
        d["duration"] = duration
    return Shot.parse(d, 0)


def spec_for(shot: Shot):
    film = Film(shots=[shot])
    got = audio.speech_specs(film, 24, lambda s: "v.wav")
    assert len(got) == 1
    _src, start, end, _delay, speed = got[0]
    return start, end, speed


@pytest.mark.parametrize("speed", [1.0, 1.08, 1.2, 1.5])
def test_the_picture_and_its_words_are_the_same_length(speed):
    shot = slide(speed)
    start, end, got_speed = spec_for(shot)
    assert got_speed == pytest.approx(speed)
    words_play_for = (end - start) / got_speed
    assert shot.duration == pytest.approx(words_play_for + VOICE_TAIL)


def test_a_faster_picture_is_a_shorter_picture():
    assert slide(1.2).duration < slide(1.0).duration
    assert slide(1.0).duration == pytest.approx(WORDS + VOICE_TAIL)
    assert slide(1.2).duration == pytest.approx(WORDS / 1.2 + VOICE_TAIL)


def test_the_words_themselves_are_still_the_words_that_were_said():
    """`in`/`out` are where the sentence is in the recording. Speeding it
    up must not go looking for different words."""
    for speed in (1.0, 1.2):
        start, end, _ = spec_for(slide(speed))
        assert (start, end) == (0.0, WORDS)


def test_holding_a_picture_longer_still_does_not_stretch_the_words():
    """The rule audio.py's comment was really defending. An explicit
    duration holds the photograph; the narration is unchanged."""
    held = slide(1.0, duration=40.0)
    assert held.duration == pytest.approx(40.0)
    start, end, speed = spec_for(held)
    assert (end - start) / speed == pytest.approx(WORDS)
