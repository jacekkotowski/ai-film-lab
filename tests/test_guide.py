"""
"What do I do next?"

The guide is the whole app for somebody in a hurry, and its failures are
all the same failure: sending you backwards. Being told to render a
rougher version of the thing you have just watched, or being sent to fill
in a folder that is already full, is what makes a person decide the tool
is arguing with them and stop using it.

Everything here builds a project out of empty files. `next_steps` reads
mtimes and names -- it never opens the footage -- so an empty .jpg is
exactly as good as a photograph, and the suite stays fast.
"""

import os
import sys
from pathlib import Path

from ffilm import guide
from ffilm.guide import next_steps


def project(root: Path, **when) -> Path:
    """A project at a given stage. `when` is file -> mtime, oldest 1."""
    for sub in ("media", "analysis", "out"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    for rel, t in when.items():
        p = root / {"media": "media/a.jpg",
                    "manifest": "analysis/manifest.json",
                    "yml": "film.yaml",
                    "peek": "out/peek.mp4",
                    "draft": "out/draft.mp4",
                    "final": "out/final.mp4",
                    "cover": "out/cover.jpg"}[rel]
        p.write_bytes(b"x")
        os.utime(p, (t, t))
    return root


def first(root: Path) -> str:
    return next_steps(root)[0].args and " ".join(next_steps(root)[0].args) or ""


def titles(root: Path) -> str:
    return " | ".join(s.title for s in next_steps(root))


# --------------------------------------------------------------------------
# The way in
# --------------------------------------------------------------------------

def test_an_empty_project_asks_for_files(tmp_path):
    steps = next_steps(project(tmp_path))
    assert steps[0].folders and steps[0].folders[0].name == "media"


def test_only_one_folder_is_opened(tmp_path):
    """The point of the shared library: music and the thumbnail picture
    are done once, so the first thing that happens to somebody is one
    Explorer window, not two."""
    steps = next_steps(project(tmp_path))
    assert len(steps[0].folders) == 1


def test_record_stays_offered_after_pressing_enter_on_empty_media(
        tmp_path, shelf, monkeypatch, capsys):
    """The bug this guards: the alternatives (chiefly `record`, the one
    real option somebody with nothing in media\\ has) were only printed
    on the FIRST card. Press ENTER again with media\\ still empty --
    the ordinary thing to do while still dragging files in -- and the
    card collapses to one nag line. `record` still worked if you typed
    its number from memory, but it had visibly vanished, which is as
    good as gone for somebody who has not memorised the menu."""
    (tmp_path / "media").mkdir(parents=True)
    monkeypatch.setattr(sys, "platform", "win32")     # record is win32-only
    answers = iter(["", "q"])                          # ENTER, then stop
    monkeypatch.setattr(guide, "_ask", lambda prompt: next(answers))
    monkeypatch.setattr(guide, "open_folder", lambda folder: None)
    fake_stdin = type("FakeStdin", (), {"isatty": lambda self: True})()
    monkeypatch.setattr(sys, "stdin", fake_stdin)

    guide.walk(tmp_path)

    out = capsys.readouterr().out
    assert out.count("say it to the camera") == 2


def test_a_full_shelf_says_there_is_nothing_to_do(tmp_path, shelf):
    (shelf / "music" / "hum.mp3").write_bytes(b"x")
    (shelf / "cover" / "wide.jpg").write_bytes(b"x")
    assert "nothing else to set up" in next_steps(project(tmp_path))[0].why


def test_an_empty_shelf_says_how_to_fill_it(tmp_path, shelf):
    why = next_steps(project(tmp_path))[0].why
    assert "film library" in why
    assert "no music and no a thumbnail" not in why      # reads as English
    assert "no music and no thumbnail picture" in why


def test_footage_with_no_analysis_offers_the_one_command(tmp_path):
    assert "go" in first(project(tmp_path, media=100))


def test_new_footage_since_the_last_look_starts_again(tmp_path):
    """Files added after the analysis must not be silently left out."""
    assert "go" in first(project(tmp_path, manifest=100, media=200))


def test_an_analysed_project_with_no_edit_writes_one(tmp_path):
    assert "init" in first(project(tmp_path, media=100, manifest=200))


# --------------------------------------------------------------------------
# Never backwards
# --------------------------------------------------------------------------

def test_an_unwatched_edit_is_peeked_at(tmp_path):
    assert "peek" in first(project(tmp_path, media=100, manifest=200, yml=300))


def test_a_draft_answers_the_order_question_too(tmp_path):
    """`go` renders a draft. Being sent back to `peek` afterwards is
    being told to render a worse version of what you just watched."""
    root = project(tmp_path, media=100, manifest=200, yml=300, draft=400)
    assert "peek" not in first(root)


def test_going_straight_to_final_is_not_sent_back_to_peek(tmp_path):
    """Somebody who knows what they want types `final`. The guide has to
    cope with that -- it used to send them back to the roughest render
    of the three."""
    root = project(tmp_path, media=100, manifest=200, yml=300, final=400)
    assert "peek" not in titles(root).lower()
    assert next_steps(root)[0].done


def test_editing_after_a_final_render_starts_the_loop_again(tmp_path):
    """The file changed, so the finished film no longer matches it."""
    root = project(tmp_path, media=100, manifest=200, final=300, yml=400)
    assert not next_steps(root)[0].done


def test_a_watched_draft_is_offered_the_ship_step(tmp_path):
    root = project(tmp_path, media=100, manifest=200, yml=300, peek=400,
                   draft=500)
    assert "final" in first(root)


# --------------------------------------------------------------------------
# The thumbnail
# --------------------------------------------------------------------------

def test_a_film_with_no_thumbnail_is_offered_one(tmp_path):
    root = project(tmp_path, media=100, manifest=200, yml=300, draft=400)
    assert "thumbnail" in titles(root)


def test_a_thumbnail_newer_than_the_edit_is_not_nagged_about(tmp_path):
    """`film final` builds one on its own, so by the time anybody could
    take this step it is usually already done."""
    root = project(tmp_path, media=100, manifest=200, yml=300, draft=400,
                   cover=500)
    assert "thumbnail" not in titles(root)


# --------------------------------------------------------------------------
# Not falling over
# --------------------------------------------------------------------------

def test_a_film_yaml_being_hand_edited_does_not_break_the_guide(tmp_path):
    """Halfway through typing, film.yaml is not valid YAML. The guide is
    what you run to find out what went wrong -- it cannot be the second
    thing that breaks."""
    root = project(tmp_path, media=100, manifest=200, yml=300, draft=400)
    (root / "film.yaml").write_text("shots: [unclosed", encoding="utf-8")
    assert next_steps(root)
