"""
Packing a copy for another computer.

The two ways this can be wrong are opposite and both quiet: leaving out
something irreplaceable, and carrying something that must not travel --
a virtual environment full of absolute paths, or the file that says
which camera this particular laptop has.
"""

import zipfile
from pathlib import Path

import pytest

from ffilm import pack
from ffilm.pack import build, contents, default_name, wanted


def toolkit(root: Path) -> Path:
    """A miniature of the real folder, junk included."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "ffilm").mkdir()
    (root / "ffilm" / "render.py").write_text("x", encoding="utf-8")
    (root / "ffilm" / "__pycache__").mkdir()
    (root / "ffilm" / "__pycache__" / "render.pyc").write_bytes(b"x")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("x", encoding="utf-8")
    (root / "pyproject.toml").write_text("x", encoding="utf-8")
    (root / "uv.lock").write_text("x", encoding="utf-8")
    (root / "FILM.bat").write_text("x", encoding="utf-8")
    (root / ".devices.json").write_text("x", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "pyvenv.cfg").write_text("x", encoding="utf-8")

    p = root / "projects" / "morning"
    (p / "media").mkdir(parents=True)
    (p / "media" / "take.mp4").write_bytes(b"x" * 100)
    (p / "music").mkdir()
    (p / "out").mkdir()
    (p / "out" / "final.mp4").write_bytes(b"x" * 5000)
    (p / "analysis" / "proxies").mkdir(parents=True)
    (p / "analysis" / "proxies" / "take.mp4").write_bytes(b"x" * 5000)
    (p / "film.yaml").write_text("fps: 24", encoding="utf-8")
    (p / "script.txt").write_text("hello", encoding="utf-8")
    return root


def names(root, projects=None):
    return {arc for _, arc in contents(root, projects)}


# --------------------------------------------------------------------------
# What must never travel
# --------------------------------------------------------------------------

def test_the_virtual_environment_is_never_packed():
    """388 MB of absolute paths baked in at build time. It would not work
    on the other machine even if it fitted."""
    assert not wanted(Path(".venv/pyvenv.cfg"))


def test_the_camera_this_laptop_happens_to_have_stays_here():
    assert not wanted(Path(".devices.json"))


def test_renders_and_analysis_are_left_behind():
    """The largest things in the folder, and both come back on their own."""
    assert not wanted(Path("projects/morning/out/final.mp4"))
    assert not wanted(Path("projects/morning/analysis/proxies/take.mp4"))


def test_compiled_python_and_editor_droppings_are_left_behind():
    assert not wanted(Path("ffilm/__pycache__/render.pyc"))
    assert not wanted(Path(".pytest_cache/v/cache/lastfailed"))
    assert not wanted(Path(".git/config"))


def test_a_zip_never_packs_another_zip():
    """Otherwise every pack is bigger than the last one."""
    assert not wanted(Path("AI-Film-2026-08-28.zip"))


# --------------------------------------------------------------------------
# What must travel
# --------------------------------------------------------------------------

def test_the_code_and_the_lockfile_go():
    assert wanted(Path("ffilm/render.py"))
    assert wanted(Path("uv.lock"))


def test_the_lockfile_is_in_the_zip(tmp_path):
    """Without it the other computer resolves its own versions, and gets
    a different toolkit. This is exactly how face detection died."""
    assert "uv.lock" in names(toolkit(tmp_path))


def test_the_toolkit_alone_carries_no_films(tmp_path):
    assert not any(n.startswith("projects/") for n in names(toolkit(tmp_path)))


def test_the_shared_library_travels_with_the_toolkit(tmp_path):
    """It belongs to no one film, so it is packed with none of them --
    and a copy that arrives without it is a copy where every film has
    quietly lost its soundtrack and its thumbnail."""
    root = toolkit(tmp_path)
    (root / "library" / "music").mkdir(parents=True)
    (root / "library" / "music" / "quiet.mp3").write_bytes(b"x" * 100)
    (root / "library" / "cover").mkdir(parents=True)
    (root / "library" / "cover" / "wide.jpg").write_bytes(b"x" * 100)
    got = names(root)
    assert "library/music/quiet.mp3" in got
    assert "library/cover/wide.jpg" in got


def test_a_packed_project_brings_its_originals_and_its_edit(tmp_path):
    got = names(toolkit(tmp_path), ["morning"])
    assert "projects/morning/media/take.mp4" in got
    assert "projects/morning/film.yaml" in got
    assert "projects/morning/script.txt" in got


def test_a_packed_project_leaves_its_renders_behind(tmp_path):
    got = names(toolkit(tmp_path), ["morning"])
    assert not any("/out/" in n or "/analysis/" in n for n in got)


def test_asking_for_a_film_that_is_not_there_says_so(tmp_path):
    with pytest.raises(SystemExit):
        contents(toolkit(tmp_path), ["nope"])


def test_a_missing_optional_part_is_not_an_error(tmp_path):
    """blender/ and data/ are listed but need not exist."""
    root = toolkit(tmp_path)
    assert "pyproject.toml" in names(root)      # got here without raising


# --------------------------------------------------------------------------
# The zip itself
# --------------------------------------------------------------------------

def test_the_zip_unpacks_into_one_folder_not_over_your_desktop(tmp_path):
    root = toolkit(tmp_path / "src")
    out = tmp_path / "AI-Film-test.zip"
    build(root, out)
    tops = {n.split("/")[0] for n in zipfile.ZipFile(out).namelist()}
    assert tops == {"AI-Film-test"}


def test_the_zip_tells_you_what_to_do_with_it(tmp_path):
    root = toolkit(tmp_path / "src")
    out = tmp_path / "AI-Film-test.zip"
    build(root, out)
    inside = zipfile.ZipFile(out).namelist()
    assert "AI-Film-test/SETUP.bat" in inside
    assert "AI-Film-test/READ_ME_FIRST.txt" in inside


def test_setup_installs_both_programs_windows_lacks():
    assert "astral-sh.uv" in pack.SETUP_BAT
    assert "Gyan.FFmpeg" in pack.SETUP_BAT
    assert "uv sync" in pack.SETUP_BAT


def test_setup_warns_about_the_window_that_cannot_see_the_new_program():
    """The single most common way a Windows install looks broken when it
    worked: PATH is read when the window opens, not after."""
    assert "CLOSE this window" in pack.SETUP_BAT


def test_the_name_says_what_is_inside():
    assert default_name(None).startswith("AI-Film-")
    assert "morning" in default_name(["morning"])
