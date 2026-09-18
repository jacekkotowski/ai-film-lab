"""
`audio_offset: 2.0` makes the narration wait two seconds. It does not
cut two seconds off the front of it.

Found on 2026-09-18, checking what a film with talking clips AND a
narration would do. `film init` writes

    audio_offset: 2.0   # the narration waits for the opening card

and the soundtrack did the opposite: it passed the offset as the point
to START READING the file, with no delay. So the narration began at
0.0 under the silent title card, with its first two seconds missing.
Measured through `audio.speech_specs` on a 61 s take: it played from
0.0 to 59.0 s. On test_story's first narration the first word is at
2.05 s -- it survived by five hundredths of a second, which is why
nobody heard it go wrong.

No film in projects/ has an `audio_offset` written by hand, so the
meaning the file has always claimed is the one that wins:

    positive   the narration starts that many seconds into the film
    negative   the first that many seconds of the recording are skipped

Everything placed on the narration's clock moves with it: the sound,
the captions fitted against it, and `film check`'s warning about a
narration longer than the film.

No ffmpeg. A few empty files where the code checks that one exists.
"""

from pathlib import Path

from pytest import approx

from ffilm import caption_fit, checks
from ffilm.audio import speech_specs
from ffilm.spec import Film, Shot
from ffilm.voice import Line


def film_with(tmp_path: Path, offset: float) -> Film:
    (tmp_path / "media").mkdir(exist_ok=True)
    (tmp_path / "media" / "vo.wav").write_bytes(b"")
    return Film(fps=24, root=tmp_path, audio="media/vo.wav",
                audio_offset=offset,
                shots=[Shot.parse({"id": "s00", "src": "card.jpg",
                                   "duration": 2.0}, 0),
                       Shot.parse({"id": "s01", "src": "a.png",
                                   "duration": 20.0}, 1)])


def narration(specs):
    return [s for s in specs if s[0].name == "vo.wav"][0]


def test_a_positive_offset_delays_the_narration(tmp_path):
    _src, start, end, delay, _speed = narration(
        speech_specs(film_with(tmp_path, 2.0), 24, lambda s: None))
    assert start == approx(0.0)        # from the very first word
    assert end is None
    assert delay == 2000               # ...two seconds into the film


def test_no_offset_is_no_delay_and_no_cut(tmp_path):
    _src, start, _end, delay, _speed = narration(
        speech_specs(film_with(tmp_path, 0.0), 24, lambda s: None))
    assert (start, delay) == (approx(0.0), 0)


def test_a_negative_offset_skips_the_start_of_the_recording(tmp_path):
    """The one way to throw away a fumbled first few seconds without
    editing the recording itself."""
    _src, start, _end, delay, _speed = narration(
        speech_specs(film_with(tmp_path, -3.5), 24, lambda s: None))
    assert (start, delay) == (approx(3.5), 0)


def test_captions_move_with_the_narration(tmp_path):
    """A line said 1.0 s into the recording is on screen at 3.0 s when
    the narration waits two seconds -- on the second shot, not the
    title card."""
    placed, _ = caption_fit.fit_global(film_with(tmp_path, 2.0),
                                       [Line("hello there", 1.0, 3.0)])
    assert "s00" not in placed
    assert placed["s01"][0].at == approx(1.0)      # 3.0 s into the film


def test_a_negative_offset_moves_the_captions_earlier(tmp_path):
    placed, _ = caption_fit.fit_global(film_with(tmp_path, -3.0),
                                       [Line("later words", 8.0, 10.0)])
    assert placed["s01"][0].at == approx(3.0)      # 8 - 3 = 5 s in film


def test_the_check_counts_the_wait_as_part_of_the_narration():
    """A 21 s narration that waits 2 s runs to 23 s: past a 22 s film."""
    assert checks.narration_note(21.0 + 2.0, 22.0) is not None
    assert checks.narration_seconds_in_film(21.0, 2.0) == approx(23.0)
    assert checks.narration_seconds_in_film(21.0, -3.0) == approx(18.0)
