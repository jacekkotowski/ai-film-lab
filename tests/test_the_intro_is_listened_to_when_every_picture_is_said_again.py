"""The intro is listened to even when every picture was said again.

Jacek, 2026-10-02, Excel Time Logic: "intro captions do not correspond to
what is being said". The intro (a camera clip) carried three captions
that were picture 1's words. Cause, measured: with every slide's `voice:`
naming its own retake, `voice_sources` returned only the retakes and
never listened to the clips -- the old narration had been captioning the
intro by film time, wrongly, and once it stopped (see
test_a_narration_no_shot_quotes_is_not_listened_to) nothing captioned
the intro at all. Clips the film uses are listened to whenever slides
carry `voice:`.
"""
from types import SimpleNamespace

from ffilm import voice


def test_a_clip_in_the_film_is_listened_to_beside_the_retakes(
        tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    for name in ("voiceover_20261002-194127.wav",
                 "picture1_20261002-200616.wav", "rec_intro.mp4"):
        (media / name).write_bytes(b"x")
    marker = voice.VoiceSource(media / "rec_intro.mp4", "rec_intro.mp4",
                               ["media/rec_intro.mp4"])
    monkeypatch.setattr(voice, "_clip_sources", lambda project, clips: (
        [marker] if [c.name for c in clips] == ["rec_intro.mp4"] else []))
    film = SimpleNamespace(
        resolve=lambda rel: tmp_path / rel,
        shots=[SimpleNamespace(voice=None, src="media/rec_intro.mp4",
                               kind="video"),
               SimpleNamespace(voice="media/picture1_20261002-200616.wav",
                               src="media/x.png", kind="image")])
    labels = sorted(s.label for s in voice.voice_sources(tmp_path, film))
    assert labels == ["picture1_20261002-200616.wav", "rec_intro.mp4"]
