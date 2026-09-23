"""The intro and the outro each have their own script.

script_intro.txt for the words said to the camera before the pictures,
script_outro.txt for the words after them. Found 2026-09-23: with no
closing words written yet, the closing window opened on script.txt --
the intro -- so the one file looked like it was still shared.
"""
from ffilm import booth, pack


def test_both_go_with_the_project_to_another_computer():
    for names in booth.PART_FILES.values():
        assert set(names) <= set(pack.PROJECT_KEEP)


def test_the_intro_is_kept_in_script_intro(tmp_path):
    assert booth.script_path(tmp_path, part="intro").name == "script_intro.txt"


def test_the_outro_is_kept_in_script_outro(tmp_path):
    assert booth.script_path(tmp_path, part="closing").name == "script_outro.txt"


def test_the_outro_never_opens_on_the_intro(tmp_path):
    (tmp_path / "script.txt").write_text("Hello, this is the intro.",
                                         encoding="utf-8")
    (tmp_path / "script_intro.txt").write_text("Hello, this is the intro.",
                                               encoding="utf-8")
    assert booth.read_script(tmp_path, None, part="closing") == ""


def test_the_two_do_not_overwrite_each_other(tmp_path):
    booth.save_script(booth.script_path(tmp_path, part="intro"), "Hello.")
    booth.save_script(booth.script_path(tmp_path, part="closing"), "Goodbye.")
    assert booth.read_script(tmp_path, None, part="intro") == "Hello."
    assert booth.read_script(tmp_path, None, part="closing") == "Goodbye."


def test_a_project_from_before_the_rename_still_opens_on_its_words(tmp_path):
    """intro.txt / closing.txt, 2026-09-23 morning; script.txt before
    that, and then only ever for the intro."""
    (tmp_path / "intro.txt").write_text("Old intro.", encoding="utf-8")
    (tmp_path / "closing.txt").write_text("Old outro.", encoding="utf-8")
    assert booth.read_script(tmp_path, None, part="intro") == "Old intro."
    assert booth.read_script(tmp_path, None, part="closing") == "Old outro."
    (tmp_path / "intro.txt").unlink()
    (tmp_path / "script.txt").write_text("Oldest intro.", encoding="utf-8")
    assert booth.read_script(tmp_path, None, part="intro") == "Oldest intro."
