"""
`film record --voice` names a take `voiceover_20260917-104512.wav`
(record.take_name, audio_only=True) -- and voice.voice_sources only
recognised a file named exactly `voiceover.*`, matched with
`.startswith("voiceover.")`. A dated one fell through to "any standalone
audio file", which still works, but stops being the outright winner the
moment a second audio file (a phone voice memo, an old recording) is
also sitting in media/ -- rule 1 is "always wins outright", rule 2 is
"first alphabetically, and says what it did NOT listen to."

Numbers and file layout only here. Nothing touches ffmpeg or a model.
"""

from pathlib import Path

from ffilm.voice import voice_sources


def project(tmp_path: Path) -> Path:
    p = tmp_path / "narrated"
    (p / "media").mkdir(parents=True)
    (p / "analysis").mkdir()
    return p


def test_a_dated_voiceover_is_still_the_narration(tmp_path):
    p = project(tmp_path)
    (p / "media" / "voiceover_20260917-104512.wav").write_bytes(b"")
    (p / "media" / "another_memo.mp3").write_bytes(b"")
    sources = voice_sources(p)
    assert len(sources) == 1
    assert sources[0].audio_path.name == "voiceover_20260917-104512.wav"


def test_an_exact_voiceover_still_wins_too(tmp_path):
    """The rule this replaces, kept working."""
    p = project(tmp_path)
    (p / "media" / "voiceover.mp3").write_bytes(b"")
    (p / "media" / "another_memo.mp3").write_bytes(b"")
    sources = voice_sources(p)
    assert sources[0].audio_path.name == "voiceover.mp3"


def test_something_merely_starting_with_voice_is_not_mistaken_for_it(tmp_path):
    """A prefix match on "voiceover", not on "voice" -- a file called
    voicemail.mp3 or voice_notes.wav is somebody else's naming, not
    what `film record --voice` writes."""
    p = project(tmp_path)
    (p / "media" / "voicemail.mp3").write_bytes(b"")
    sources = voice_sources(p)
    assert sources[0].audio_path.name == "voicemail.mp3"   # falls to rule 2
    assert len(sources) == 1
