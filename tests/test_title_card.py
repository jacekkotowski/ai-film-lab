"""
The opening card -- the film's name over the thumbnail picture, held for
four seconds before anybody speaks.

It is DERIVED, and that is the whole risk in it. film.yaml points at a
file in analysis/, and analysis/ is the folder that gets deleted: it is
regenerable by design, it is in .gitignore, and `film pack` leaves it
behind. A film that will not open because its own opening shot has been
tidied away would be the worst kind of bug -- so most of what is below
is about the card coming back on its own.
"""

from pathlib import Path

from PIL import Image

from ffilm import cover
from ffilm.scaffold import TITLE_CARD_SECONDS, title_card_block


def picture(path: Path, w: int, h: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (70, 90, 110)).save(path)
    return path


def project(tmp_path: Path, name: str = "late_walk") -> Path:
    p = tmp_path / name
    (p / "analysis").mkdir(parents=True)
    (p / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    return p


def stocked(shelf: Path) -> None:
    picture(shelf / "cover" / "a_wide.jpg", 1600, 900)
    picture(shelf / "cover" / "b_tall.jpg", 900, 1600)


# --------------------------------------------------------------------------
# Making it
# --------------------------------------------------------------------------

def test_the_card_is_the_shape_of_the_film(tmp_path, shelf):
    stocked(shelf)
    p = project(tmp_path)
    assert cover.build_card(p, 1080, 1920) is not None
    with Image.open(cover.card_path(p)) as im:
        assert im.size == (1080, 1920)


def test_a_widescreen_film_gets_a_widescreen_card(tmp_path, shelf):
    stocked(shelf)
    p = project(tmp_path)
    cover.build_card(p, 1920, 1080)
    with Image.open(cover.card_path(p)) as im:
        assert im.size == (1920, 1080)


def test_with_no_picture_anywhere_there_is_no_card(tmp_path, shelf):
    """A film opening on a title over black is a thing somebody might
    choose. It is not a thing to hand them unasked."""
    assert cover.build_card(project(tmp_path), 1080, 1920) is None


def test_the_card_is_referred_to_by_a_relative_path(tmp_path, shelf):
    """film.yaml has to survive the project folder being moved, or
    zipped and opened on another computer."""
    assert not Path(cover.card_src(project(tmp_path))).is_absolute()


def test_the_card_lands_where_film_yaml_says_it_does(tmp_path, shelf):
    stocked(shelf)
    p = project(tmp_path)
    cover.build_card(p, 1080, 1920)
    assert (p / cover.card_src(p)).exists()


# --------------------------------------------------------------------------
# Making it again
# --------------------------------------------------------------------------

def test_a_deleted_analysis_folder_does_not_cost_you_the_film(tmp_path, shelf):
    """The one that matters. analysis/ is regenerable by design, so it
    gets deleted -- and the film must not stop opening because of it."""
    stocked(shelf)
    p = project(tmp_path)
    cover.build_card(p, 1080, 1920)
    cover.card_path(p).unlink()
    assert cover.refresh_card(p, 1080, 1920) is not None
    assert cover.card_path(p).exists()


def test_changing_the_title_changes_the_card(tmp_path, shelf):
    """Otherwise the film opens on the old name and the thumbnail shows
    the new one, which is worse than either alone."""
    import os
    stocked(shelf)
    p = project(tmp_path)
    cover.build_card(p, 1080, 1920)
    before = cover.card_path(p).read_bytes()

    (p / "film.yaml").write_text("title: Something Else\n", encoding="utf-8")
    os.utime(cover.card_path(p), (1, 1))          # now older than the edit
    cover.refresh_card(p, 1080, 1920)
    assert cover.card_path(p).read_bytes() != before


def test_a_card_that_is_already_right_is_not_rebuilt(tmp_path, shelf):
    """It is made before every render. Redrawing it each time would be
    work for nothing."""
    import os
    stocked(shelf)
    p = project(tmp_path)
    cover.build_card(p, 1080, 1920)
    os.utime(p / "film.yaml", (1, 1))             # the edit is older
    stamp = cover.card_path(p).stat().st_mtime
    cover.refresh_card(p, 1080, 1920)
    assert cover.card_path(p).stat().st_mtime == stamp


def test_refreshing_with_nothing_to_draw_on_is_not_a_crash(tmp_path, shelf):
    assert cover.refresh_card(project(tmp_path), 1080, 1920) is None


# --------------------------------------------------------------------------
# What init writes
# --------------------------------------------------------------------------

def test_init_opens_the_film_on_the_card(tmp_path, shelf):
    stocked(shelf)
    block = "\n".join(title_card_block(project(tmp_path), vertical=True))
    assert "src: analysis/title.jpg" in block
    assert f"duration: {TITLE_CARD_SECONDS:.1f}" in block


def test_the_card_never_moves(tmp_path, shelf):
    """Every move but static scales into the frame, and the frame is a
    title: push in on it at all and the words lose their edges."""
    stocked(shelf)
    block = "\n".join(title_card_block(project(tmp_path), vertical=True))
    assert "move: static" in block


def test_a_film_with_nothing_to_put_on_a_card_simply_has_no_card(tmp_path,
                                                                 shelf):
    assert title_card_block(project(tmp_path), vertical=True) == []


def test_the_block_says_how_to_get_rid_of_it(tmp_path, shelf):
    """It is a shot in film.yaml like any other. Somebody who would
    rather open on their own face has to be told they can just delete
    it -- that is the difference between a default and a decision."""
    stocked(shelf)
    block = "\n".join(title_card_block(project(tmp_path), vertical=True))
    assert "delete this whole" in block


def test_the_note_survives_being_read_back_as_yaml(tmp_path, shelf):
    """It is written by hand as text, over four lines, with quotes in
    the middle of it. That is exactly the sort of thing that produces a
    film.yaml nothing can open."""
    import yaml
    stocked(shelf)
    p = project(tmp_path)
    text = "shots:\n" + "\n".join(title_card_block(p, vertical=True)) + "\n"
    shot = yaml.safe_load(text)["shots"][0]
    assert shot["src"] == "analysis/title.jpg"
    assert shot["duration"] == TITLE_CARD_SECONDS
    assert "thumbnail" in shot["note"]
