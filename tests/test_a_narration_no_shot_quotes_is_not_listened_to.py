"""A narration no shot quotes any more is not listened to.

Jacek, 2026-10-02, Excel Time Logic: "the draft shows overlapping
captions as if two versions of captions existed". Two did. He said all
five pictures again, so every slide's `voice:` named its own retake and
none named the whole narration. `voice_sources` then took the whole
narration for a GLOBAL track -- one file under the whole film, matched
against the film's clock -- and put its 34 lines on whatever shot was on
screen at those times, on top of each retake's own captions. Measured on
the film: s02 had 7 captions of its retake and 6 of the old narration
(overlapping by up to 3.8 s); s04 had 21 where 10 belonged.

A global narration is a film with NO slides carrying `voice:`. A film
whose slides carry `voice:` and none of them quote the narration has
moved past it: its words are the retakes'.
"""
from types import SimpleNamespace

from ffilm import voice


def _project(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    for name in ("voiceover_20261002-194127.wav",
                 "picture1_20261002-200616.wav",
                 "picture2_20261002-200842.wav"):
        (media / name).write_bytes(b"RIFF")
    return tmp_path


def _film(project, voices):
    shots = [SimpleNamespace(voice=v, src="media/x.png", kind="image")
             for v in voices]
    return SimpleNamespace(
        shots=shots, resolve=lambda rel: project / rel)


def _labels(sources):
    return sorted(s.label for s in sources)


def test_every_picture_said_again_leaves_the_old_narration_unheard(tmp_path):
    p = _project(tmp_path)
    film = _film(p, ["media/picture1_20261002-200616.wav",
                     "media/picture2_20261002-200842.wav"])
    assert _labels(voice.voice_sources(p, film)) == [
        "picture1_20261002-200616.wav", "picture2_20261002-200842.wav"]


def test_a_narration_one_slide_still_quotes_is_still_heard(tmp_path):
    p = _project(tmp_path)
    film = _film(p, ["media/voiceover_20261002-194127.wav",
                     "media/picture2_20261002-200842.wav"])
    assert "voiceover_20261002-194127.wav" in _labels(
        voice.voice_sources(p, film))


def test_a_narration_under_a_film_with_no_slides_is_still_heard(tmp_path):
    p = _project(tmp_path)
    film = _film(p, [None, None])
    assert "voiceover_20261002-194127.wav" in _labels(
        voice.voice_sources(p, film))
