"""
A film with narrated pictures and talking clips gets captions from both.

`voice.voice_sources` used to let a `voiceover` file win outright: when
there was a narration, the sound in the clips was never listened to.
That was right while the narration played flat under everything -- the
two would have competed. Since 2026-09-18 a narration is cut across the
pictures and each clip keeps its own sound, so the words spoken in a
clip were simply never captioned.

Now, when the narration is carried by slides, every clip in the film
that has a sound track is a source as well, each fitted to its own
shots. A narration still laid flat under the film (`audio:`) keeps the
old rule.

ffprobe and the audio extraction are stood in for; nothing is decoded.
"""

from pathlib import Path

from ffilm import voice
from ffilm.spec import Film, Shot


def project(tmp_path: Path) -> Path:
    media = tmp_path / "media"
    media.mkdir()
    for n in ("a.png", "voiceover_1.wav", "rec_1.mp4", "rec_unused.mp4"):
        (media / n).write_bytes(b"x")
    return tmp_path


def fake_audio(monkeypatch):
    monkeypatch.setattr(voice, "has_audio_track", lambda p: True)
    monkeypatch.setattr(voice, "extract_audio", lambda video, out: out)


def slide_film(root: Path) -> Film:
    return Film(root=root, shots=[
        Shot.parse({"id": "s01", "src": "media/a.png",
                    "voice": "media/voiceover_1.wav", "in": 0.0,
                    "out": 5.0}, 0),
        Shot.parse({"id": "s02", "src": "media/rec_1.mp4", "in": 0.0,
                    "out": 4.0}, 1)])


def test_a_slide_film_is_captioned_from_its_narration_and_its_clips(
        tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    p = project(tmp_path)
    sources = voice.voice_sources(p, slide_film(p))
    labels = [s.label for s in sources]
    assert labels[0] == "voiceover_1.wav"
    assert "rec_1.mp4" in labels


def test_each_source_is_matched_to_its_own_shots(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    p = project(tmp_path)
    by = {s.label: s.shot_srcs for s in voice.voice_sources(p, slide_film(p))}
    assert by["voiceover_1.wav"] == ["media/voiceover_1.wav"]
    assert by["rec_1.mp4"] == ["media/rec_1.mp4"]


def test_a_clip_not_in_the_film_is_not_transcribed(tmp_path, monkeypatch):
    """Listening costs minutes. A clip no shot uses has nothing to be
    captioned onto."""
    fake_audio(monkeypatch)
    p = project(tmp_path)
    labels = [s.label for s in voice.voice_sources(p, slide_film(p))]
    assert "rec_unused.mp4" not in labels


def test_a_flat_narration_still_wins_outright(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    p = project(tmp_path)
    flat = Film(root=p, audio="media/voiceover_1.wav", shots=[
        Shot.parse({"id": "s01", "src": "media/a.png", "duration": 5.0}, 0),
        Shot.parse({"id": "s02", "src": "media/rec_1.mp4", "in": 0.0,
                    "out": 4.0}, 1)])
    assert [s.label for s in voice.voice_sources(p, flat)] == \
        ["voiceover_1.wav"]
