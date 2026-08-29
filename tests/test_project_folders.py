"""
Making a project, and the thumbnail that appears without being asked.

Four commands used to create the same five folders, each with its own
copy of the list and its own copy of the comment explaining why cover/
is one of them. That is the shape of bug where `film drop` quietly stops
making somewhere to put the music, and nothing says so until a film comes
out silent.
"""

from pathlib import Path

from PIL import Image

from ffilm import cli, cover


def picture(path: Path, w: int, h: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (90, 110, 130)).save(path)
    return path


# --------------------------------------------------------------------------
# The folders
# --------------------------------------------------------------------------

def test_a_new_project_has_every_folder_it_needs(tmp_path):
    root = cli.make_project(tmp_path / "morning")
    for sub in cli.PROJECT_DIRS:
        assert (root / sub).is_dir(), sub


def test_a_vertical_project_is_marked_as_one(tmp_path):
    root = cli.make_project(tmp_path / "short", vertical=True)
    assert (root / ".vertical").exists()


def test_a_widescreen_project_is_not(tmp_path):
    root = cli.make_project(tmp_path / "wide")
    assert not (root / ".vertical").exists()


def test_making_a_project_twice_loses_nothing(tmp_path):
    """`film record` calls this on a folder that may already be there."""
    root = cli.make_project(tmp_path / "again")
    (root / "media" / "take.mp4").write_bytes(b"x")
    cli.make_project(root)
    assert (root / "media" / "take.mp4").exists()


def test_the_shape_is_settled_once_and_not_revisited(tmp_path):
    """`film shape --wide` removes the marker. `film record` on the same
    project must not put it back and quietly turn the film sideways."""
    root = cli.make_project(tmp_path / "wide_now", vertical=True)
    (root / ".vertical").unlink()
    cli.make_project(root, vertical=True)
    assert not (root / ".vertical").exists()


def test_making_a_project_stocks_the_shelf(tmp_path, shelf):
    """So that the two folders you fill in once exist before anybody goes
    looking for them."""
    cli.make_project(tmp_path / "morning")
    assert (shelf / "music").is_dir()
    assert (shelf / "cover").is_dir()


# --------------------------------------------------------------------------
# The shape of the film decides the shape of the cover
# --------------------------------------------------------------------------

def test_a_vertical_project_with_no_film_yaml_is_still_vertical(tmp_path):
    root = cli.make_project(tmp_path / "short", vertical=True)
    assert cli._film_shape(root) == (1080, 1920)


def test_the_resolution_in_film_yaml_wins(tmp_path):
    root = cli.make_project(tmp_path / "short", vertical=True)
    (root / "film.yaml").write_text("resolution: [1920, 1080]\n",
                                    encoding="utf-8")
    assert cli._film_shape(root) == (1920, 1080)


def test_a_nonsense_resolution_falls_back_rather_than_crashing(tmp_path):
    root = cli.make_project(tmp_path / "odd")
    (root / "film.yaml").write_text("resolution: yes please\n",
                                    encoding="utf-8")
    assert cli._film_shape(root) == cover.WIDE


# --------------------------------------------------------------------------
# The thumbnail nobody asked for
# --------------------------------------------------------------------------

def test_final_builds_a_thumbnail_from_the_shelf(tmp_path, shelf, capsys):
    picture(shelf / "cover" / "a_wide.jpg", 1600, 900)
    picture(shelf / "cover" / "b_tall.jpg", 900, 1600)
    root = cli.make_project(tmp_path / "late_walk", vertical=True)
    (root / "film.yaml").write_text("resolution: [1080, 1920]\n",
                                    encoding="utf-8")

    cli.auto_cover(root)
    out = cover.out_path(root)
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (1080, 1920)
    assert "Late Walk" in capsys.readouterr().out


def test_nothing_is_built_when_there_is_no_picture(tmp_path, shelf):
    """A title on black is a thing somebody might want, but not a thing
    to hand them unasked."""
    root = cli.make_project(tmp_path / "bare")
    (root / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    cli.auto_cover(root)
    assert not cover.out_path(root).exists()


def test_a_thumbnail_made_by_hand_is_not_replaced(tmp_path, shelf):
    """The whole reason auto_cover checks staleness: somebody who ran
    `film cover --title "..."` must not lose it to the next render."""
    import os
    picture(shelf / "cover" / "wide.jpg", 1600, 900)
    root = cli.make_project(tmp_path / "mine")
    (root / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    os.utime(root / "film.yaml", (1, 1))
    out = cover.out_path(root)
    out.write_bytes(b"my own cover")

    cli.auto_cover(root)
    assert out.read_bytes() == b"my own cover"


def test_an_unreadable_picture_costs_you_the_cover_not_the_render(tmp_path,
                                                                  shelf,
                                                                  capsys):
    """Forty minutes of rendering must not be thrown away because the
    thumbnail picture turned out to be a renamed text file."""
    (shelf / "cover" / "broken.jpg").write_bytes(b"not a picture")
    root = cli.make_project(tmp_path / "unlucky")
    (root / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    cli.auto_cover(root)
    assert "no thumbnail" in capsys.readouterr().out
