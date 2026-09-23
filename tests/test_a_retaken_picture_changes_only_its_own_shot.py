"""A retaken picture changes only its own shot.

`film record --voice --picture 4` records the words over picture 4
alone. Found 2026-09-23: Turn Heat Into Images took 10 narration takes
in a morning, each about 3 minutes, because a fluffed sentence over one
picture meant reading all six again.

The retake is its own file, picture4_<time>.wav, with the picture it
belongs to written beside it. Its shot in film.yaml points at it; no
other shot, move, focus or caption changes.
"""
from pathlib import Path

from ffilm import kinds, scaffold
from ffilm.spec import Film
from ffilm.voice import Line

FILM = """\
# the header stays
fps: 24
shots:

  - id: s01
    src: media/0_rec.mp4
    move: static

  - id: s02
    src: media/1_oil.jpg
    voice: media/voiceover_1.wav
    in: "00:00.00"
    out: "00:20.55"
    speed: 1.2
    move: tilt_up
    focus: [0.4, 0.5]
    captions:
      - text: "Old words one."
        at: 0.73
        dur: 2.28
      - text: "Old words two."
        at: 3.0
        dur: 1.0

  - id: s03
    src: media/2_thermo.jfif
    voice: media/voiceover_1.wav
    in: "00:22.30"
    out: "00:45.80"
    move: push_in
    captions:
      - text: "Keep me."
        at: 1.0
        dur: 2.0

# 3 shots, about 50 seconds.
"""


def _film(tmp_path, text=FILM):
    (tmp_path / "media").mkdir(exist_ok=True)
    for name in ("0_rec.mp4", "1_oil.jpg", "2_thermo.jfif",
                 "voiceover_1.wav", "picture1_20260923-150000.wav",
                 "picture1_x.wav"):
        (tmp_path / "media" / name).write_bytes(b"")
    p = tmp_path / "film.yaml"
    p.write_text(text, encoding="utf-8")
    return Film.load(p)


def test_pictures_are_counted_as_the_notes_count_them(tmp_path):
    """Picture 1 is the first shot with words over a photo, not the
    first shot: the talking head before it is not a picture."""
    shots = scaffold.picture_shots(_film(tmp_path))
    assert [s.id for s in shots] == ["s02", "s03"]


def test_only_that_shot_points_at_the_new_take(tmp_path):
    film = _film(tmp_path)
    cut = scaffold.retake_cut(film, 1, "media/picture1_20260923-150000.wav",
                              0.4, 12.6)
    text = scaffold.retake_text(FILM, cut, [])
    assert "voice: media/picture1_20260923-150000.wav" in text
    assert 'in: "00:00.40"' in text
    assert text.count("voice: media/voiceover_1.wav") == 1     # s03's
    assert "move: tilt_up" in text and "focus: [0.4, 0.5]" in text
    assert "speed: 1.2" in text
    assert text.startswith("# the header stays")
    assert "# 3 shots, about 50 seconds." in text


def test_its_old_captions_go_and_the_others_stay(tmp_path):
    film = _film(tmp_path)
    cut = scaffold.retake_cut(film, 1, "media/picture1_x.wav", 0.0, 10.0)
    from ffilm.spec import Caption
    text = scaffold.retake_text(FILM, cut, [Caption(text="New words.",
                                                    at=0.5, dur=2.0)])
    assert "Old words" not in text
    assert "New words." in text
    assert "Keep me." in text
    reloaded = _film(tmp_path, text)
    by_id = {s.id: s for s in reloaded.shots}
    assert [c.text for c in by_id["s02"].captions] == ["New words."]
    assert [c.text for c in by_id["s03"].captions] == ["Keep me."]


def test_the_picture_is_chosen_by_what_was_said(tmp_path):
    menu = scaffold.picture_menu(_film(tmp_path))
    assert menu == ["  1  1_oil.jpg  'Old words one.'",
                    "  2  2_thermo.jfif  'Keep me.'"]


def test_a_picture_the_film_does_not_have_is_said_plainly(tmp_path):
    assert scaffold.retake_cut(_film(tmp_path), 7, "media/x.wav", 0, 1) is None


def test_the_silence_before_and_after_the_words_is_not_kept():
    """You press record, breathe, talk, stop. The breath and the reach
    for SPACE are not the picture's words."""
    lines = [Line(start=1.2, end=3.0, text="a"), Line(start=3.5, end=9.8,
                                                      text="b")]
    assert scaffold.speech_window(lines, 11.0) == (0.9, 10.1)
    assert scaffold.speech_window([], 11.0) == (0.0, 11.0)
    assert scaffold.speech_window(
        [Line(start=0.1, end=10.9, text="a")], 11.0) == (0.0, 11.0)


def test_a_retake_is_never_taken_for_the_whole_narration():
    files = [Path("media/voiceover_20260923-123826.wav"),
             Path("media/picture4_20260923-150000.wav")]
    assert kinds.pick_narration(files, when=lambda p: {
        files[0]: 1.0, files[1]: 2.0}[p]) == files[0]
    assert kinds.is_picture_retake(files[1])
    assert not kinds.is_picture_retake(files[0])


def test_a_new_whole_narration_puts_the_picture_retakes_aside():
    """Read again from the start, every picture's words are new; a
    retake of one picture from before would put the old reading back."""
    files = [Path("media/picture4_20260923-150000.wav"),
             Path("media/picture4_20260923-150000.picture.json"),
             Path("media/voiceover_20260923-160000.wav")]
    assert sorted(kinds.older_narrations(files, files[2])) == \
        sorted(files[:2])


def test_a_rewrite_keeps_a_retaken_picture(tmp_path):
    """`go --rewrite` cuts every picture from the narration again; it
    used to have no way to know picture 1 had been said again since."""
    import os
    from ffilm import record
    _film(tmp_path)
    media = tmp_path / "media"
    take = media / "picture1_20260923-150000.wav"
    record.write_retake(take, "media/1_oil.jpg", 0.4, 12.6)
    os.utime(media / "voiceover_1.wav", (100, 100))
    os.utime(take, (200, 200))
    text = scaffold.keep_retakes(tmp_path, FILM)
    assert "voice: media/picture1_20260923-150000.wav" in text
    assert 'out: "00:12.60"' in text
    assert text.count("voice: media/voiceover_1.wav") == 1

    os.utime(take, (50, 50))          # older than the narration
    assert scaffold.keep_retakes(tmp_path, FILM) == FILM


def test_the_newest_retake_of_each_picture_since_the_narration_wins():
    found = [("media/picture4_a.wav", "media/4.jfif", 10.0),
             ("media/picture4_b.wav", "media/4.jfif", 20.0),
             ("media/picture2_a.wav", "media/2.jfif", 5.0),   # before it
             ("media/picture1_a.wav", "media/1.jpg", 30.0)]
    assert scaffold.latest_retakes(found, since=8.0) == {
        "media/4.jfif": "media/picture4_b.wav",
        "media/1.jpg": "media/picture1_a.wav"}
