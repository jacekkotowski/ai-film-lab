"""
What a person is told, on the way from photographs to a narrated film.

The machine can now cut a narration into one slide per picture, and a
script's paragraphs say where the cuts go. None of that is any use if
nobody is ever told it exists. Three places say so, and this pins what
each one says:

  the recording window, before a word is spoken, so somebody pasting a
  script knows a blank line is what changes the picture;
  the guide, afterwards, which must send them to `go` -- the step that
  captions -- and not to `init`, which does not;
  `film check`, which has to show a slide's words or there is no way to
  see what a shot is holding without opening the file.

Strings and numbers. Nothing opens a window or a camera.
"""

from pathlib import Path

from ffilm import booth, checks, guide
from ffilm.spec import Film, Shot


# --------------------------------------------------------------------------
# The recording window, before anybody speaks
# --------------------------------------------------------------------------

def test_a_voiceover_over_photographs_is_told_what_a_blank_line_does():
    said = booth.compose_hint(voice_only=True)
    assert "paragraph" in said.lower()
    assert "picture" in said.lower()
    # And how to move on: SPACE, since 2026-09-18. It used to say the
    # pictures changed at the longest pauses, which was the guess `init`
    # made before there was a Next button.
    assert "space" in said.lower()


def test_talking_to_the_camera_is_told_none_of_that():
    """There are no pictures to change. A prompt about paragraphs and
    photographs in front of somebody about to talk to a lens is just
    noise."""
    said = booth.compose_hint(voice_only=False)
    assert "paragraph" not in said.lower()
    assert "just speak" in said.lower()


# --------------------------------------------------------------------------
# What `film check` shows for a slide
# --------------------------------------------------------------------------

def slide_film() -> Film:
    return Film(shots=[
        Shot(src="analysis/title.jpg", kind="still", duration=2.0,
             move="static", id="s00"),
        Shot(src="media/1declaration_of_love.png", kind="still",
             voice="media/vo.wav", tin=2.05, tout=18.20, duration=16.55,
             move="drift_left", id="s01")])


def test_a_slide_shows_the_words_it_is_holding():
    lines = checks.shot_lines(slide_film())
    assert "voice 00:02.05-00:18.20" in lines[1]
    assert "1declaration_of_love.png" in lines[1]


def test_a_shot_with_no_words_shows_none():
    assert "voice" not in checks.shot_lines(slide_film())[0]


def test_the_captions_are_still_counted():
    from ffilm.spec import Caption
    film = slide_film()
    film.shots[1].captions = [Caption(text="a"), Caption(text="b")]
    assert "2 caption(s)" in checks.shot_lines(film)[1]


# --------------------------------------------------------------------------
# Where the guide sends somebody after they record a narration
# --------------------------------------------------------------------------

def narrated(tmp_path: Path) -> Path:
    """A project with an edit, and a voiceover recorded after it. The
    times matter: the manifest is newer than the media, film.yaml newer
    than that, and the narration newest of all."""
    import json
    import os

    p = tmp_path / "narrated"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    (p / "out").mkdir()
    at = {}
    at[media / "a.png"] = 100
    at[p / "analysis" / "manifest.json"] = 200
    at[p / "film.yaml"] = 300
    at[media / "voiceover_20260917-105656.wav"] = 400

    (media / "a.png").write_bytes(b"x")
    (p / "analysis" / "manifest.json").write_text(
        json.dumps({"count": 1, "unreadable": [],
                    "media": [{"path": "media/a.png", "kind": "still",
                               "focus": [0.5, 0.5]}]}), encoding="utf-8")
    (p / "film.yaml").write_text(
        "fps: 24\nshots:\n  - id: s01\n    src: media/a.png\n"
        "    duration: 4.5\n", encoding="utf-8")
    (media / "voiceover_20260917-105656.wav").write_bytes(b"x")
    for path, when in at.items():
        os.utime(path, (when, when))
    return p


def test_a_narration_recorded_after_the_edit_sends_you_to_go(tmp_path):
    """`init --force` writes the slides but does NOT caption them, so
    the words were on the soundtrack and never on the screen. `go` does
    ingest, init, caption and a draft, which is the whole job."""
    steps = guide.next_steps(narrated(tmp_path))
    assert steps[0].args[0] == "go"
    assert "--rewrite" in steps[0].args


def test_the_step_says_the_old_edit_is_kept(tmp_path):
    why = guide.next_steps(narrated(tmp_path))[0].why
    assert "film.yaml.bak" in why
