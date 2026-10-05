"""
A long pause inside the narration over a picture is shortened, and every
caption stays on the word it was written for.

Why this is a command: a slide has one `in`/`out` pair into the
narration, so a pause INSIDE one picture's words could not be cut by any
edit of film.yaml. Measured on SUMIFS SUMPRODUCT vs DAX (2026-10-05):
30 pauses of 0.6 s or more inside the six narrated pictures, 30.5 s of
recording; cutting each to 0.4 s saves 15.5 s as played. Every one of
them measured -56.6 to -45.7 dB median inside, against a speech line of
-41.1 dB (docs/tech/audio.md).

So `film tighten` writes a shorter copy of the narration (the original in
media/ is never touched) and moves every number that points into it: the
pictures' in/out, and each caption's at, dur and words. A caption's
times are film seconds, (source - in) / speed, so each is mapped through
the cut in SOURCE seconds and divided again.
"""

import numpy as np
import pytest

from ffilm.spec import Film
from ffilm.tighten import cuts_for, moved, retime_text, splice

YAML = """\
fps: 24

shots:

  - id: s01
    src: media/rec_1.mp4
    in: "00:01.00"
    out: "00:31.00"
    speed: 1.2              # 1.0 is the speed you actually spoke at
    move: static
    captions:
      - text: "camera"
        at: 5.00
        dur: 2.00
        words: [0.00, 1.00]

  - id: s02
    src: media/pic.png
    voice: media/voiceover_1.wav
    in: "00:00.00"
    out: "01:00.00"
    speed: 1.2              # 1.0 is the speed you actually read at
    move: columns
    note: "picture 1 of 2"
    captions:
      - text: "one"
        at: 10.00
        dur: 2.00
        words: [0.00, 1.00]
      - text: "two, across a pause"
        at: 20.00
        dur: 5.00
        words: [0.00, 3.00]

  - id: s03
    src: media/pic2.png
    voice: media/voiceover_1.wav
    in: "01:02.00"
    out: "01:30.00"
    speed: 1.2
    move: columns
    captions:
      - text: "three"
        at: 1.00
        dur: 2.00

# 3 shots.
"""

VOICE = "media/voiceover_1.wav"
NEW = "analysis/tight/voiceover_1__tight_0123abcd.wav"
CUTS = [(5.0, 6.0), (25.0, 26.0), (70.0, 71.0)]     # 3 s of source


def load(tmp_path, text):
    yml = tmp_path / "film.yaml"
    yml.write_text(text, encoding="utf-8")
    return Film.load(yml, check_files=False)


def test_only_a_long_pause_well_inside_a_picture_is_cut():
    quiet = [(1.0, 2.0),      # 1.0 s inside: cut, 0.2 s kept each side
             (3.0, 3.3),      # 0.3 s: a breath, kept
             (9.6, 10.5),     # runs past the picture's out: not touched
             (12.0, 14.0)]    # between pictures, never played: not touched
    windows = [(0.5, 10.0), (14.5, 20.0)]
    assert cuts_for(quiet, windows, over=0.6, keep=0.4) == [
        pytest.approx((1.2, 1.8))]


def test_a_moment_moves_back_by_what_was_cut_before_it():
    assert moved(4.0, CUTS) == pytest.approx(4.0)
    assert moved(5.5, CUTS) == pytest.approx(5.0)      # inside a cut
    assert moved(10.0, CUTS) == pytest.approx(9.0)
    assert moved(80.0, CUTS) == pytest.approx(77.0)


def test_every_caption_stays_on_the_same_word_of_the_recording(tmp_path):
    film = load(tmp_path, YAML)
    after = load(tmp_path, retime_text(YAML, film, VOICE, NEW, CUTS))
    for a, b in zip(film.shots, after.shots):
        if a.voice != VOICE:
            continue
        assert b.voice == NEW
        assert b.tin == pytest.approx(moved(a.tin, CUTS), abs=0.01)
        assert b.tout == pytest.approx(moved(a.tout, CUTS), abs=0.01)
        for ca, cb in zip(a.captions, b.captions):
            src = lambda t, sh=a: sh.tin + t * sh.speed
            new = lambda t, sh=b: sh.tin + t * sh.speed
            assert new(cb.at) == pytest.approx(moved(src(ca.at), CUTS), abs=0.01)
            assert new(cb.at + cb.dur) == pytest.approx(
                moved(src(ca.at + ca.dur), CUTS), abs=0.01)
            for wa, wb in zip(ca.words, cb.words):
                assert new(cb.at + wb) == pytest.approx(
                    moved(src(ca.at + wa), CUTS), abs=0.015)


def test_the_film_is_shorter_by_the_cut_at_its_speed(tmp_path):
    film = load(tmp_path, YAML)
    after = load(tmp_path, retime_text(YAML, film, VOICE, NEW, CUTS))
    assert film.duration - after.duration == pytest.approx(3.0 / 1.2, abs=0.02)


def test_a_camera_take_and_everything_else_are_not_touched(tmp_path):
    film = load(tmp_path, YAML)
    out = retime_text(YAML, film, VOICE, NEW, CUTS)
    s01 = YAML.split("  - id: s02")[0]
    assert out.startswith(s01)
    assert '    note: "picture 1 of 2"' in out
    assert out.rstrip().endswith("# 3 shots.")


def test_the_sound_is_shorter_by_exactly_the_cut():
    rate = 1000
    x = np.arange(10 * rate, dtype=np.int16).reshape(-1, 1)
    y = splice(x, rate, [(2.0, 3.0), (6.0, 6.5)])
    assert len(y) == len(x) - int(1.5 * rate)
    # what is kept is kept as it was, away from the joins
    assert (y[100:1900, 0] == x[100:1900, 0]).all()
    assert (y[2100:4900, 0] == x[3100:5900, 0]).all()
