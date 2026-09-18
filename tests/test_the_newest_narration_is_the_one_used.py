"""
When media/ holds more than one narration, the newest is the one used.

Found on 2026-09-18. Jacek recorded test_story again, pressing Next
between the pictures, and ran `go --rewrite`. The film came back built
from the PREVIOUS day's take: `voiceover_20260917-105656.wav` sorted
before `voiceover_20260918-103350.wav`, and both `scaffold.build` and
`voice.voice_sources` took the first file in alphabetical order. Today's
recording and the places he pressed Next were saved and never used.

Recording again is how anybody says "not that one, this one". So: the
file most recently written wins, and a name that starts `voiceover`
beats one that does not, as it always has. Both callers ask the same
function, so the soundtrack and the captions can never pick different
takes.

The clock is handed in; nothing here reads a real file's time.
"""

from pathlib import Path

from ffilm import kinds


def when_from(times: dict):
    return lambda p: times[Path(p).name]


def test_the_most_recent_take_wins():
    old = Path("media/voiceover_20260917-105656.wav")
    new = Path("media/voiceover_20260918-103350.wav")
    got = kinds.pick_narration([old, new], when_from({old.name: 100.0,
                                                      new.name: 200.0}))
    assert got == new


def test_alphabetical_order_does_not_decide_it():
    """A later-written file whose name sorts first still wins."""
    a = Path("media/voiceover_aaa.wav")
    z = Path("media/voiceover_zzz.wav")
    assert kinds.pick_narration([a, z], when_from({a.name: 300.0,
                                                   z.name: 100.0})) == a


def test_a_file_named_voiceover_beats_any_other_audio():
    """A newer mp3 dropped in media/ is not the narration if a file
    says outright that it is."""
    vo = Path("media/voiceover.wav")
    memo = Path("media/memo.mp3")
    assert kinds.pick_narration([vo, memo], when_from({vo.name: 100.0,
                                                       memo.name: 900.0})) == vo


def test_with_no_voiceover_the_newest_audio_is_used():
    a = Path("media/memo_1.mp3")
    b = Path("media/memo_2.mp3")
    assert kinds.pick_narration([a, b], when_from({a.name: 500.0,
                                                   b.name: 100.0})) == a


def test_only_audio_is_ever_a_narration():
    """The recording window writes `voiceover_....cues.json` beside a
    take. It is not a narration, whatever its name starts with."""
    wav = Path("media/voiceover_1.wav")
    cues = Path("media/voiceover_1.cues.json")
    assert kinds.pick_narration([wav, cues], when_from({wav.name: 1.0,
                                                        cues.name: 9.0})) == wav


def test_nothing_to_pick_is_none():
    assert kinds.pick_narration([], lambda p: 0.0) is None


def test_init_and_the_captions_pick_the_same_take(tmp_path):
    """The two callers used to do this separately. Now they cannot
    disagree: the film's soundtrack and its captions come from one
    file."""
    import json
    import os

    from ffilm import scaffold, voice

    p = tmp_path / "p"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    (media / "a.png").write_bytes(b"x")
    old = media / "voiceover_20260917-105656.wav"
    new = media / "voiceover_20260918-103350.wav"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    os.utime(old, (100, 100))
    os.utime(new, (200, 200))
    (p / "analysis" / "manifest.json").write_text(json.dumps(
        {"media": [{"path": "media/a.png", "kind": "still",
                    "focus": [0.5, 0.5]}]}), encoding="utf-8")

    assert scaffold.narration_of(p) == new
    assert voice.voice_sources(p)[0].audio_path == new

    # And the film says so, so an older take is not a mystery.
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(scaffold, "narration_pauses", lambda path: (0.5, 9.5, []))
    mp.setattr(scaffold, "narration_seconds", lambda path: 10.0)
    try:
        text = scaffold.build(p)
    finally:
        mp.undo()
    assert "voice: media/voiceover_20260918-103350.wav" in text
    assert "The newest of 2 recordings" in text
