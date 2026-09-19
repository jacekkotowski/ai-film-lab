"""
`film init` cuts a narration into one piece per picture.

Before this, a project of photographs with a voiceover got `audio:` --
one track laid flat under the whole film -- and the pictures stretched
evenly to cover it. On `projects/test_story` that was 23.3 / 19.1 /
19.1 seconds against a narration whose sentences fall at 1.8, 19.7,
30.2, 40.9 and 54.7. Nothing lined up, and there was nothing in
film.yaml to line up BY.

So: when there are photographs and a narration and no script, the
narration is cut at its longest pauses, one piece per picture, and each
picture becomes a slide holding its own words. Exactly what already
happens to a talking take, which is cut at its pauses into one shot per
piece -- same constants, same breath either side of the cut.

The pauses measured on test_story's own 59.5s narration, for the
numbers used below: the three longest are 34.45-37.40, 7.70-9.55 and
10.25-12.20. Three pictures means two cuts, at the longest two.

Everything here works off a pause list handed in. Nothing decodes
audio.
"""

import json
from pathlib import Path

from PIL import Image
from pytest import approx

from ffilm import scaffold
from ffilm.scaffold import BREATH, MIN_SHOT, cut_at_pauses
from ffilm.spec import VOICE_TAIL, Film


# --------------------------------------------------------------------------
# Where the cuts go
# --------------------------------------------------------------------------

# The real thing, as ingest measured it: (first word, last word, pauses)
STORY = (1.84, 57.25, [(7.70, 9.55), (10.25, 12.20), (18.60, 19.40),
                       (28.90, 30.05), (34.45, 37.40), (44.60, 45.75),
                       (50.60, 51.80)])


def test_one_picture_takes_the_whole_narration():
    assert cut_at_pauses(*STORY, 1) == [(approx(1.84 - BREATH),
                                         approx(57.25 + BREATH))]


def test_three_pictures_are_cut_at_the_two_longest_pauses():
    pieces = cut_at_pauses(*STORY, 3)
    assert len(pieces) == 3
    # The longest pause is 34.45-37.40 (2.95s), then 10.25-12.20 (1.95s).
    assert pieces[0][1] == approx(10.25 + BREATH)
    assert pieces[1][0] == approx(12.20 - BREATH)
    assert pieces[1][1] == approx(34.45 + BREATH)
    assert pieces[2][0] == approx(37.40 - BREATH)


def test_the_pieces_run_in_order_and_never_overlap():
    pieces = cut_at_pauses(*STORY, 4)
    assert len(pieces) == 4
    for (_a, b), (c, _d) in zip(pieces, pieces[1:]):
        assert c >= b            # the gap between them is the pause


def test_every_word_is_inside_some_piece():
    """A cut takes a BREATH off each side of the pause and no more. What
    is dropped is silence; nothing that was said goes missing."""
    pieces = cut_at_pauses(*STORY, 4)
    gaps = [(b, c) for (_a, b), (c, _d) in zip(pieces, pieces[1:])]
    for gap_start, gap_end in gaps:
        assert any(s <= gap_start and gap_end <= e for s, e in STORY[2])


def test_the_first_and_last_piece_keep_a_breath_of_their_own():
    pieces = cut_at_pauses(*STORY, 3)
    assert pieces[0][0] == approx(1.84 - BREATH)
    assert pieces[-1][1] == approx(57.25 + BREATH)


def test_a_cut_that_would_leave_a_sliver_is_not_made():
    """A pause right next to the first word is the longest one there is,
    and cutting at it would make a picture that is on screen for half a
    second. The next-longest pause is used instead."""
    pieces = cut_at_pauses(1.0, 40.0, [(1.4, 9.0), (20.0, 21.0)], 2)
    assert len(pieces) == 2
    assert pieces[0][1] == approx(20.0 + BREATH)
    assert all(b - a >= MIN_SHOT for a, b in pieces)


def test_more_pictures_than_pauses_gives_fewer_pieces():
    """Five pictures and one usable pause is two pieces, not five empty
    ones. The caller is told how many it actually got."""
    pieces = cut_at_pauses(1.0, 40.0, [(20.0, 21.0)], 5)
    assert len(pieces) == 2


def test_a_narration_with_no_pauses_at_all_is_one_piece():
    assert len(cut_at_pauses(1.0, 40.0, [], 3)) == 1


# --------------------------------------------------------------------------
# What `film init` then writes
# --------------------------------------------------------------------------

def picture(path: Path, w: int, h: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (70, 90, 110)).save(path)
    return path


def story(tmp_path: Path) -> Path:
    """test_story's shape: three numbered pictures and a voiceover."""
    p = tmp_path / "test_story"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    (p / ".vertical").write_text("", encoding="utf-8")
    names = ["1declaration_of_love.png", "2declaration of love.png",
             "3_declaration_of_love.png"]
    for n in names:
        picture(media / n, 900, 1600)
    (media / "voiceover_20260917-105656.wav").write_bytes(b"")
    (p / "analysis" / "manifest.json").write_text(json.dumps({"media": [
        {"path": f"media/{n}", "kind": "still", "focus": [0.5, 0.5]}
        for n in names]}), encoding="utf-8")
    return p


def built(tmp_path, monkeypatch, pauses=STORY, duration=59.5) -> str:
    monkeypatch.setattr(scaffold, "narration_pauses",
                        lambda path: (pauses[0], pauses[1], pauses[2]))
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: duration)
    return scaffold.build(story(tmp_path))


def test_each_picture_gets_its_own_words(tmp_path, monkeypatch):
    text = built(tmp_path, monkeypatch)
    assert text.count("voice: media/voiceover_20260917-105656.wav") == 3
    assert 'in: "00:01.54"' in text
    assert 'out: "00:10.55"' in text


def test_the_pictures_stay_in_the_order_they_were_numbered(tmp_path,
                                                            monkeypatch):
    text = built(tmp_path, monkeypatch)
    order = [ln.split("src: ")[1] for ln in text.splitlines()
             if "src: media/" in ln]
    assert order == ["media/1declaration_of_love.png",
                     "media/2declaration of love.png",
                     "media/3_declaration_of_love.png"]


def test_the_flat_narration_track_is_gone(tmp_path, monkeypatch):
    """`audio:` plays under everything and cannot be edited. A film made
    of slides must not have both -- it would say every word twice."""
    text = built(tmp_path, monkeypatch)
    assert "\naudio:" not in text
    assert "audio_offset:" not in text


def test_it_no_longer_claims_the_captions_were_left_out(tmp_path,
                                                        monkeypatch):
    text = built(tmp_path, monkeypatch)
    assert "Speech captions are left out on purpose" not in text


def test_it_says_what_it_did_and_how_to_do_better(tmp_path, monkeypatch):
    text = built(tmp_path, monkeypatch)
    assert "3 slide(s), one per picture" in text
    assert "the 60s narration" in text
    assert "GUESSED" in text
    assert "narration.txt" in text


def test_the_film_it_writes_loads_and_holds_every_word(tmp_path,
                                                        monkeypatch):
    p = story(tmp_path)
    monkeypatch.setattr(scaffold, "narration_pauses",
                        lambda path: STORY)
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: 59.5)
    (p / "film.yaml").write_text(scaffold.build(p), encoding="utf-8")
    film = Film.load(p / "film.yaml")

    slides = [s for s in film.shots if s.voice]
    assert len(slides) == 3
    assert slides[0].tin == approx(1.84 - BREATH)
    assert slides[-1].tout == approx(57.25 + BREATH)
    for s in slides:
        assert s.duration == approx((s.tout - s.tin) + VOICE_TAIL)
    # No overlap, and in order.
    for a, b in zip(slides, slides[1:]):
        assert b.tin >= a.tout


def test_a_clip_in_the_film_does_not_stop_the_pictures_being_slides(
        tmp_path, monkeypatch):
    """Reversed on 2026-09-18. This used to pin the opposite -- a film
    with any footage kept one flat narration track -- and measured on a
    real clip that put two voices on top of each other for 5.8 s. The
    narration is now cut across the pictures only, and the clip keeps
    its own sound. See test_talking_clips_and_narrated_pictures_share_a_film.py."""
    p = story(tmp_path)
    manifest = json.loads((p / "analysis" / "manifest.json")
                          .read_text(encoding="utf-8"))
    manifest["media"].append({"path": "media/walk.mp4", "kind": "video",
                              "duration": 8.0, "focus": [0.5, 0.5],
                              "cuts": []})
    (p / "analysis" / "manifest.json").write_text(json.dumps(manifest),
                                                  encoding="utf-8")
    (p / "media" / "walk.mp4").write_bytes(b"")
    monkeypatch.setattr(scaffold, "narration_pauses", lambda path: STORY)
    monkeypatch.setattr(scaffold, "narration_seconds", lambda path: 59.5)
    text = scaffold.build(p)
    assert "\naudio:" not in text
    assert text.count("voice: media/voiceover_20260917-105656.wav") == 3
