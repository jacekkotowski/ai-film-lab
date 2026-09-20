"""
A film can hold your talking clips AND photographs you narrated.

Measured on 2026-09-18 with a scratch project -- test_story's three
pictures, its narration with Next pressed twice, and one real talking
take from Morning_2026-09-05. One talking clip switched everything
narrated off: `init` required every shot to be a photograph before it
would cut the narration into slides. So the presses were ignored, the
narration went back to one flat track under the whole film, and the
clip's own speech played over the end of it -- both voices at once from
53.2 s to 59.0 s.

A clip already carries its own sound; a slide carries its piece of the
narration. They are the same kind of shot with the sound in a different
file, and `audio.speech_specs` already places both on one timeline. So:
the narration is cut across the PICTURES only, and every clip stays
where the filename order put it, with its own sound. Nobody talks over
anybody.

Pause lists and a few small files. Nothing decodes audio.
"""

import json
from pathlib import Path

from PIL import Image
from pytest import approx

from ffilm import record, scaffold
from ffilm.audio import speech_specs
from ffilm.spec import Film

NAMES = ["1a.png", "2b.png", "3c.png"]
WAV = "voiceover_20260918-103350.wav"
CLIP = "rec_20260905-164940.mp4"
PAUSES = [(15.0, 16.2), (37.0, 38.3)]


def mixed(tmp_path: Path, cues=True, clip_first=False, names=NAMES) -> Path:
    p = tmp_path / "mixed"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    for n in names:
        Image.new("RGB", (900, 1600), (70, 90, 110)).save(media / n)
    (media / WAV).write_bytes(b"x")
    (media / CLIP).write_bytes(b"x")
    clip = {"path": f"media/{CLIP}", "kind": "video", "duration": 12.0,
            "focus": [0.5, 0.4], "cuts": [],
            "sound": {"has": True, "ratio": 0.8, "in": 0.2, "out": 11.8,
                      "quiet": []}}
    stills = [{"path": f"media/{n}", "kind": "still", "focus": [0.5, 0.5]}
              for n in names]
    entries = [clip] + stills if clip_first else stills + [clip]
    (p / "analysis" / "manifest.json").write_text(
        json.dumps({"media": entries}), encoding="utf-8")
    if cues:
        record.write_cues(media / WAV, [15.52, 37.52],
                          [f"media/{n}" for n in names])
    return p


def built(p: Path, monkeypatch) -> Film:
    monkeypatch.setattr(scaffold, "narration_pauses",
                        lambda path: (0.8, 60.2, PAUSES))
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: 61.0)
    (p / "film.yaml").write_text(scaffold.build(p), encoding="utf-8")
    return Film.load(p / "film.yaml")


def test_the_pictures_become_slides_even_with_a_clip_in_the_film(
        tmp_path, monkeypatch):
    film = built(mixed(tmp_path), monkeypatch)
    slides = [s for s in film.shots if s.voice]
    assert [Path(s.src).name for s in slides] == NAMES
    assert slides[0].tout == approx(15.0 + scaffold.BREATH)
    assert film.audio is None           # no flat track under everything


def test_the_clip_keeps_its_own_place_and_its_own_sound(tmp_path,
                                                         monkeypatch):
    film = built(mixed(tmp_path), monkeypatch)
    clips = [s for s in film.shots if s.kind == "video"]
    assert clips and all(s.voice is None for s in clips)
    # Recorded 2026-09-05, before the 2026-09-18 narration, so it opens
    # the film -- it used to follow the numbered pictures. See
    # test_takes_play_where_you_recorded_them.
    assert Path(clips[0].src).name == CLIP
    assert film.shots.index(clips[0]) < min(
        film.shots.index(s) for s in film.shots if s.voice)


def test_a_clip_that_comes_first_stays_first(tmp_path, monkeypatch):
    """Unnumbered files keep the order ingest found them in, and here
    that puts the clip first. (A numbered picture always comes before
    anything unnumbered -- that is what the number is for.)"""
    plain = ["a.png", "b.png", "c.png"]
    film = built(mixed(tmp_path, clip_first=True, names=plain), monkeypatch)
    assert film.shots[0].kind == "video"
    assert [Path(s.src).name for s in film.shots if s.voice] == plain


def test_nobody_talks_over_anybody(tmp_path, monkeypatch):
    """Every piece of speech, narration or clip, ends before the next
    one starts, on the film's own clock."""
    film = built(mixed(tmp_path), monkeypatch)
    specs = speech_specs(film, 24, lambda s: Path(s.voice or s.src))
    spans = sorted((d / 1000, d / 1000 + (b - a) / sp)
                   for _src, a, b, d, sp in specs)
    assert len(spans) >= 4
    for (s0, e0), (s1, _e1) in zip(spans, spans[1:]):
        assert e0 <= s1 + 1e-6


def test_without_presses_the_pictures_are_cut_at_the_pauses(tmp_path,
                                                            monkeypatch):
    film = built(mixed(tmp_path, cues=False), monkeypatch)
    assert len([s for s in film.shots if s.voice]) == 3


def test_every_shot_has_its_own_id(tmp_path, monkeypatch):
    film = built(mixed(tmp_path), monkeypatch)
    ids = [s.id for s in film.shots]
    assert len(ids) == len(set(ids))


def test_a_length_target_never_shortens_a_slide_below_its_words(
        tmp_path, monkeypatch):
    """--target shortens photographs to fit a Short. A slide's length is
    its words; shortening it would put the next shot's picture over
    them. It is treated like speech: never cut to hit a number."""
    p = mixed(tmp_path)
    monkeypatch.setattr(scaffold, "narration_pauses",
                        lambda path: (0.8, 60.2, PAUSES))
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: 61.0)
    (p / "film.yaml").write_text(scaffold.build(p, target=30.0),
                                 encoding="utf-8")
    film = Film.load(p / "film.yaml")
    for s in film.shots:
        if s.voice:
            # Played seconds, not source seconds: the narration now
            # carries the same speed correction your takes do, so
            # the words take (out - in) / speed on screen.
            assert s.duration >= (s.tout - s.tin) / s.speed - 1e-6
