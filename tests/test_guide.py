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


# --------------------------------------------------------------------------
# Not sending anybody to a step that cannot work
# --------------------------------------------------------------------------

def test_a_quarantined_take_does_not_count_as_footage(tmp_path):
    """media/_unreadable/ is where ingest puts what it could not read.
    It is inside media/, so a plain rglob finds it -- and then a project
    holding nothing but one broken take looks like a project with
    footage in it, and the guide walks you on to `init`."""
    root = project(tmp_path)
    bad = root / "media" / guide.kinds.UNREADABLE_DIRNAME
    bad.mkdir(parents=True)
    (bad / "rec_dead.mp4").write_bytes(b"x")
    steps = next_steps(root)
    assert steps[0].folders, "should still be asking for material"
    assert "init" not in " ".join(steps[0].args)


def test_an_ingest_that_found_nothing_does_not_offer_init(tmp_path):
    """`init` refuses with "No usable media found", which is correct of
    it and useless as a next step: pressing ENTER failed, the retry
    offered the same step, and it failed again. A guide that can only
    offer the thing that cannot work is worse than no guide."""
    root = project(tmp_path, media=1, manifest=2)
    (root / "analysis" / "manifest.json").write_text(
        '{"count": 0, "unreadable": ["rec_dead.mp4"], "media": []}',
        encoding="utf-8")
    steps = next_steps(root)
    assert "init" not in " ".join(steps[0].args)
    assert steps[0].folders, "should send you back for material"


def test_it_says_why_the_folder_is_not_empty_but_useless(tmp_path):
    """"Drag your photos in", over a folder that already has a file in
    it, reads as though nothing happened."""
    root = project(tmp_path, media=1, manifest=2)
    (root / "analysis" / "manifest.json").write_text(
        '{"count": 0, "unreadable": ["rec_dead.mp4"], "media": []}',
        encoding="utf-8")
    assert "could not be read" in next_steps(root)[0].why


# --------------------------------------------------------------------------
# Naming a film you did not want to name
# --------------------------------------------------------------------------

def test_the_default_name_is_the_time_of_day_and_the_date():
    from datetime import datetime
    assert guide.default_name(datetime(2026, 9, 5, 9, 30)) == \
        "Morning_2026-09-05"
    assert guide.default_name(datetime(2026, 9, 5, 14, 0)) == \
        "Afternoon_2026-09-05"
    assert guide.default_name(datetime(2026, 9, 5, 20, 0)) == \
        "Evening_2026-09-05"


def test_the_small_hours_are_night_at_both_ends_of_the_day():
    from datetime import datetime
    assert guide.part_of_day(datetime(2026, 9, 5, 2, 0)) == "Night"
    assert guide.part_of_day(datetime(2026, 9, 5, 23, 0)) == "Night"
    assert guide.part_of_day(datetime(2026, 9, 5, 5, 0)) == "Morning"


def test_the_date_sorts_as_text():
    """ISO order, so a folder listing is already in the right order."""
    from datetime import datetime
    names = [guide.default_name(datetime(2026, m, 5, 9)) for m in (1, 9, 12)]
    assert names == sorted(names)


def test_a_second_film_in_the_same_afternoon_gets_its_own_name():
    """Two films in one afternoon is an ordinary thing to do. Handing
    back the first one's name would open it again instead."""
    from datetime import datetime
    when = datetime(2026, 9, 5, 14, 0)
    first = guide.default_name(when)
    assert guide.default_name(when, taken=[first]) == first + "_2"
    assert guide.default_name(when, taken=[first, first + "_2"]) == first + "_3"


def test_a_name_written_as_words_stays_words():
    """The project name IS the film's title, and a title is written with
    spaces. Turning them into underscores and title-casing them back
    gives `Zima Nad Morzem` for a Polish name that was already correct.

    Spaces were banned here for a while because the guide prints
    commands to be retyped, and `-p Morning 2026-09-15` reads as a
    project called Morning plus a stray argument. That belongs in
    Step.pretty, which quotes it -- not here."""
    assert guide.tidy_name("Zima nad morzem") == "Zima nad morzem"
    assert guide.tidy_name("  two   words  ") == "two words"


def test_only_what_windows_refuses_is_taken_out():
    assert guide.tidy_name('a/b:c*d') == "a b c d"
    assert guide.tidy_name("..hidden..") == "hidden"


def test_a_name_of_nothing_but_punctuation_falls_back(tmp_path):
    assert guide.tidy_name("   ") == ""
    assert guide.tidy_name("///") == ""


def test_a_printed_command_can_be_retyped(tmp_path):
    """The command is printed so it can be learned and typed. A film
    whose name has a space in it printed `-p Morning 2026`, which reads
    as a project called Morning and a stray argument."""
    root = tmp_path / "Morning 2026"
    steps = next_steps(project(root))
    assert '"Morning 2026"' in steps[-1].pretty or not steps[-1].args


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


# --------------------------------------------------------------------------
# Handing the film to YouTube
# --------------------------------------------------------------------------

def test_a_landscape_film_is_not_a_short():
    from ffilm import cover
    assert cover.shorts_problems(1920, 1080, 30.0) != []
    assert cover.shorts_problems(1080, 1920, 30.0) == []


def test_a_long_film_still_uploads_it_just_is_not_a_short():
    from ffilm import cover
    note = " ".join(cover.shorts_problems(1080, 1920, 400.0))
    assert "will still upload" in note


def test_a_film_with_no_sound_is_worth_mentioning():
    from ffilm import cover
    assert cover.shorts_problems(1080, 1920, 30.0, has_audio=False) != []
