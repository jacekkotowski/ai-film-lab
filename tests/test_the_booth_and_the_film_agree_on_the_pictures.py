"""
The recording window and `film init` agree on which picture is which.

The booth is about to show the photographs one at a time while somebody
narrates them. If it shows them in one order and `init` builds the film
in another, the words said over picture 2 end up under picture 3, and
nothing on screen would say why.

So there is one rule, in scaffold, and both use it:

  the order of the pictures -- numbered files first by their number,
  then openers, the rest, closers, exactly as `init` lays out a film;
  which picture goes with which paragraph -- in order, unless the
  paragraph names one with `[3]` or `[3_name.png]`, and the last
  picture again when the paragraphs run over.

The booth sits on the same layer as scaffold and cannot import it, so
`film record` asks scaffold and hands the booth the finished list.

Files on disk for the ordering; nothing is decoded.
"""

import json
from pathlib import Path

from ffilm import scaffold
from ffilm.voice import script_paragraphs


def project(tmp_path: Path, *names: str, manifest: list[str] | None = None) -> Path:
    p = tmp_path / "p"
    media = p / "media"
    media.mkdir(parents=True)
    for n in names:
        (media / n).write_bytes(b"x")
    if manifest is not None:
        (p / "analysis").mkdir()
        (p / "analysis" / "manifest.json").write_text(json.dumps({"media": [
            {"path": f"media/{n}", "kind": "still"} for n in manifest]}),
            encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# The order of the pictures
# --------------------------------------------------------------------------

def test_numbered_pictures_come_in_their_numbers_order(tmp_path):
    p = project(tmp_path, "3_c.png", "1a.png", "2 b.png")
    assert scaffold.pictures_in_order(p) == [
        "media/1a.png", "media/2 b.png", "media/3_c.png"]


def test_an_opener_comes_first_and_a_closer_last(tmp_path):
    p = project(tmp_path, "close_end.jpg", "middle.jpg", "open_start.jpg")
    assert scaffold.pictures_in_order(p) == [
        "media/open_start.jpg", "media/middle.jpg", "media/close_end.jpg"]


def test_unnumbered_pictures_keep_the_order_ingest_found(tmp_path):
    """ingest orders by when the shutter fired, where it can. `init`
    builds from that order, so the booth has to use it too."""
    p = project(tmp_path, "a.jpg", "b.jpg", "c.jpg",
                manifest=["c.jpg", "a.jpg", "b.jpg"])
    assert scaffold.pictures_in_order(p) == [
        "media/c.jpg", "media/a.jpg", "media/b.jpg"]


def test_a_picture_that_arrived_after_ingest_is_not_forgotten(tmp_path):
    p = project(tmp_path, "a.jpg", "b.jpg", manifest=["a.jpg"])
    assert scaffold.pictures_in_order(p) == ["media/a.jpg", "media/b.jpg"]


def test_only_photographs_and_never_a_discarded_one(tmp_path):
    p = project(tmp_path, "a.jpg", "voiceover.wav", "walk.mp4")
    (p / "media" / "_discarded").mkdir()
    (p / "media" / "_discarded" / "old.jpg").write_bytes(b"x")
    assert scaffold.pictures_in_order(p) == ["media/a.jpg"]


# --------------------------------------------------------------------------
# One step per picture, with the words that go with it
# --------------------------------------------------------------------------

PICS = ["media/1a.png", "media/2b.png", "media/3c.png"]


def test_each_picture_gets_its_paragraph_in_order():
    steps = scaffold.narration_steps(PICS, script_paragraphs(
        "First one.\n\nSecond one.\n\nThird one."))
    assert steps == [("media/1a.png", "First one."),
                     ("media/2b.png", "Second one."),
                     ("media/3c.png", "Third one.")]


def test_with_no_script_every_picture_is_still_a_step():
    steps = scaffold.narration_steps(PICS, [])
    assert [s[0] for s in steps] == PICS
    assert all(text == "" for _pic, text in steps)


def test_a_paragraph_that_names_its_picture_shows_that_one():
    steps = scaffold.narration_steps(PICS, script_paragraphs(
        "[3] Start at the end.\n\nThen this."))
    assert steps[0] == ("media/3c.png", "Start at the end.")


def test_more_paragraphs_than_pictures_shows_the_last_picture_again():
    steps = scaffold.narration_steps(PICS[:2], script_paragraphs(
        "One.\n\nTwo.\n\nThree."))
    assert [s[0] for s in steps] == ["media/1a.png", "media/2b.png",
                                     "media/2b.png"]


def test_more_pictures_than_paragraphs_shows_the_rest_with_no_words():
    steps = scaffold.narration_steps(PICS, script_paragraphs("Only one."))
    assert steps[1] == ("media/2b.png", "")
    assert steps[2] == ("media/3c.png", "")


def test_no_pictures_means_no_steps():
    """Nothing to look at -- the booth behaves exactly as before."""
    assert scaffold.narration_steps([], script_paragraphs("Words.")) == []


def test_the_film_picks_pictures_by_the_same_rule():
    """slide_cuts, which re-cuts a film by paragraph, and the booth must
    never disagree about which picture a paragraph belongs to."""
    paras = script_paragraphs("[3] End.\n\nMiddle.\n\nStart.")
    for i, para in enumerate(paras):
        assert scaffold.picture_for(i, para, PICS) == \
            scaffold.narration_steps(PICS, paras)[i][0]
