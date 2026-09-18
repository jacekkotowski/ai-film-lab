"""
The film changes picture where Next was pressed.

The recording window now writes `<take>.cues.json` beside a narration:
the moments SPACE was pressed, on the take's own clock, and the picture
that was on screen for each stretch. That is the most direct statement
anybody can make about where a picture changes -- more direct than a
script's paragraphs, which have to be found in the audio, and far more
than the longest pauses, which are a guess. So:

    cues  beat  script paragraphs  beat  pauses

A press is rarely exactly in the silence. People press a little after
the sentence ends, or a little before. So each cue moves to the nearest
pause within CUE_SNAP seconds, and the cut is made there the usual way:
a breath either side, the silence between dropped. With no pause that
close, the cut is made where the key was pressed.

Numbers and a few small files. Nothing decodes audio.
"""

import json
from pathlib import Path

from PIL import Image
from pytest import approx

from ffilm import record, scaffold
from ffilm.scaffold import BREATH, CUE_SNAP, cut_at_cues
from ffilm.spec import Film, Shot

PAUSES = [(7.70, 9.55), (18.20, 20.10), (39.55, 41.25), (50.55, 52.70)]


# --------------------------------------------------------------------------
# Where the cuts go
# --------------------------------------------------------------------------

def test_a_press_inside_a_pause_cuts_in_that_pause():
    pieces = cut_at_cues([19.0], 2.05, 58.5, PAUSES)
    assert pieces == [(approx(2.05 - BREATH), approx(18.20 + BREATH)),
                      (approx(20.10 - BREATH), approx(58.5 + BREATH))]


def test_a_press_just_after_the_sentence_moves_back_to_its_pause():
    """Pressed 0.9 s after the pause ended -- still that pause."""
    pieces = cut_at_cues([21.0], 2.05, 58.5, PAUSES)
    assert pieces[0][1] == approx(18.20 + BREATH)


def test_a_press_far_from_any_pause_cuts_where_it_was_pressed():
    pieces = cut_at_cues([30.0], 2.05, 58.5, PAUSES)
    assert pieces[0][1] == approx(30.0)
    assert pieces[1][0] == approx(30.0)
    assert 30.0 - 20.10 > CUE_SNAP and 39.55 - 30.0 > CUE_SNAP


def test_one_piece_more_than_there_were_presses():
    assert len(cut_at_cues([19.0, 40.0], 2.05, 58.5, PAUSES)) == 3


def test_the_pieces_run_in_order_and_never_overlap():
    pieces = cut_at_cues([8.0, 19.0, 40.0, 51.0], 2.05, 58.5, PAUSES)
    for (_a, b), (c, _d) in zip(pieces, pieces[1:]):
        assert c >= b


def test_a_picture_nothing_was_said_over_has_no_piece():
    """Next pressed before the first word: picture 1 was on screen, but
    nobody spoke over it. It is not given half a second of silence."""
    pieces = cut_at_cues([1.0, 19.0], 2.05, 58.5, PAUSES)
    assert pieces[0] is None
    assert pieces[1][0] == approx(2.05 - BREATH)


def test_two_presses_on_one_pause_leave_the_middle_picture_empty():
    pieces = cut_at_cues([18.5, 19.5], 2.05, 58.5, PAUSES)
    assert pieces[1] is None
    assert len(pieces) == 3


# --------------------------------------------------------------------------
# What `film init` writes from them
# --------------------------------------------------------------------------

NAMES = ["1declaration_of_love.png", "2declaration of love.png",
         "3_declaration_of_love.png"]
WAV = "voiceover_20260919-101500.wav"


def story(tmp_path: Path, cues=None, pictures=None) -> Path:
    p = tmp_path / "test_story"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    (p / ".vertical").write_text("", encoding="utf-8")
    for n in NAMES:
        Image.new("RGB", (900, 1600), (70, 90, 110)).save(media / n)
    (media / WAV).write_bytes(b"")
    (p / "analysis" / "manifest.json").write_text(json.dumps({"media": [
        {"path": f"media/{n}", "kind": "still", "focus": [0.5, 0.5]}
        for n in NAMES]}), encoding="utf-8")
    if cues is not None:
        record.write_cues(media / WAV, cues,
                          pictures or [f"media/{n}" for n in NAMES])
    return p


def built(p: Path, monkeypatch) -> Film:
    monkeypatch.setattr(scaffold, "narration_pauses",
                        lambda path: (2.05, 58.5, PAUSES))
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: 59.5)
    (p / "film.yaml").write_text(scaffold.build(p), encoding="utf-8")
    return Film.load(p / "film.yaml")


def slides(film: Film) -> list[Shot]:
    return [s for s in film.shots if s.voice]


def test_the_slides_are_cut_where_next_was_pressed(tmp_path, monkeypatch):
    film = built(story(tmp_path, cues=[19.0, 40.0]), monkeypatch)
    s = slides(film)
    assert len(s) == 3
    assert s[0].tout == approx(18.20 + BREATH)
    assert s[1].tin == approx(20.10 - BREATH)
    assert s[1].tout == approx(39.55 + BREATH)
    assert s[2].tin == approx(41.25 - BREATH)


def test_the_picture_on_screen_is_the_picture_in_the_film(tmp_path,
                                                           monkeypatch):
    """The window showed 3, then 1, then 2 -- a paragraph named [3]. The
    film follows what was on screen, not the filename order."""
    shown = [f"media/{NAMES[2]}", f"media/{NAMES[0]}", f"media/{NAMES[1]}"]
    film = built(story(tmp_path, cues=[19.0, 40.0], pictures=shown),
                 monkeypatch)
    assert [s.src for s in slides(film)] == shown


def test_the_last_picture_shown_twice_is_in_the_film_twice(tmp_path,
                                                           monkeypatch):
    shown = [f"media/{NAMES[0]}", f"media/{NAMES[1]}", f"media/{NAMES[1]}"]
    film = built(story(tmp_path, cues=[19.0, 40.0], pictures=shown),
                 monkeypatch)
    assert [s.src for s in slides(film)] == shown
    ids = [s.id for s in film.shots]
    assert len(ids) == len(set(ids))


def test_a_picture_never_reached_stays_in_the_film_silent(tmp_path,
                                                          monkeypatch):
    """One press, three pictures: picture 3 was never on screen. It is
    still in media/, so it is still in the film -- after the words, as a
    plain photograph -- rather than quietly dropped."""
    film = built(story(tmp_path, cues=[19.0],
                       pictures=[f"media/{NAMES[0]}", f"media/{NAMES[1]}"]),
                 monkeypatch)
    assert len(slides(film)) == 2
    assert film.shots[-1].src == f"media/{NAMES[2]}"
    assert film.shots[-1].voice is None


def test_the_file_says_the_cuts_are_yours(tmp_path, monkeypatch):
    p = story(tmp_path, cues=[19.0, 40.0])
    built(p, monkeypatch)
    text = (p / "film.yaml").read_text(encoding="utf-8")
    assert "pressed Next" in text
    assert "GUESSED" not in text


def test_with_no_cues_it_still_guesses_from_the_pauses(tmp_path, monkeypatch):
    p = story(tmp_path)
    built(p, monkeypatch)
    assert "GUESSED" in (p / "film.yaml").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# `film caption --apply` keeps them
# --------------------------------------------------------------------------

def test_a_film_cut_by_hand_is_known_as_one(tmp_path, monkeypatch):
    film = built(story(tmp_path, cues=[19.0, 40.0]), monkeypatch)
    assert scaffold.cut_by_hand(film)


def test_a_film_cut_by_guessing_is_not(tmp_path, monkeypatch):
    film = built(story(tmp_path), monkeypatch)
    assert not scaffold.cut_by_hand(film)
