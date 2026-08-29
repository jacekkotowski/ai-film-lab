"""
The cover -- the miniature you upload beside the film.

The thing a cover must never do is be part of the film, and the thing it
must always do is stay legible at the size of a fingernail. Everything
below is one of those two.
"""

import numpy as np
from PIL import Image, ImageDraw

from ffilm import cover, kinds, library
from ffilm.cover import (MAX_BYTES, TITLE_MAX_BLOCK, TITLE_MAX_LINES,
                         TITLE_MAX_WIDTH, Backdrop, choose, fill, find_image,
                         is_stale, layout_title, save, scrim, title_from)


def draw():
    return ImageDraw.Draw(Image.new("RGBA", (8, 8)))


def photo(w, h, value=200):
    return np.full((h, w, 3), value, dtype=np.uint8)


# --------------------------------------------------------------------------
# Cropping to shape
# --------------------------------------------------------------------------

def test_a_landscape_photo_fills_a_vertical_cover():
    out = fill(photo(4000, 3000), 1080, 1920)
    assert out.shape[:2] == (1920, 1080)


def test_a_vertical_photo_fills_a_widescreen_cover():
    out = fill(photo(3000, 4000), 1280, 720)
    assert out.shape[:2] == (720, 1280)


def test_a_small_picture_is_enlarged_rather_than_bordered():
    """A cover with black bars down the side reads as a mistake."""
    out = fill(photo(320, 240), 1280, 720)
    assert out.shape[:2] == (720, 1280)


def test_nothing_is_ever_letterboxed():
    """Every pixel of the output comes from the photograph. If any row or
    column were padding it would be black, and none of them are."""
    out = fill(photo(4000, 1000, value=200), 1080, 1920)
    assert out.min() == 200


def test_a_photo_already_the_right_shape_is_left_the_right_shape():
    out = fill(photo(1080, 1920), 1080, 1920)
    assert out.shape[:2] == (1920, 1080)


# --------------------------------------------------------------------------
# Choosing the picture and the words
# --------------------------------------------------------------------------

def test_no_cover_folder_is_not_an_error(tmp_path):
    """Every project made before this existed has no cover/ folder."""
    assert find_image(tmp_path) is None


def test_an_empty_cover_folder_is_not_an_error(tmp_path):
    (tmp_path / "cover").mkdir()
    assert find_image(tmp_path) is None


def test_the_first_picture_alphabetically_wins(tmp_path):
    """So putting 01_ in front of one of them chooses between them, the
    same way it orders the film."""
    d = tmp_path / "cover"
    d.mkdir()
    (d / "02_second.jpg").write_bytes(b"x")
    (d / "01_first.jpg").write_bytes(b"x")
    assert find_image(tmp_path).name == "01_first.jpg"


def test_a_stray_text_file_in_the_cover_folder_is_ignored(tmp_path):
    d = tmp_path / "cover"
    d.mkdir()
    (d / "notes.txt").write_bytes(b"x")
    assert find_image(tmp_path) is None


def test_a_gif_may_back_a_cover(tmp_path):
    """OpenCV cannot decode one, Pillow can, and the cover is the one
    path that goes through Pillow anyway."""
    d = tmp_path / "cover"
    d.mkdir()
    (d / "loop.gif").write_bytes(b"x")
    assert find_image(tmp_path).name == "loop.gif"


def test_a_gif_is_still_not_allowed_to_be_a_shot():
    """The other half of the same decision: found by the cover, invisible
    to ingest, because a shot OpenCV cannot open is a hole in the film."""
    assert ".gif" in kinds.POSTER
    assert ".gif" not in kinds.MEDIA


# --------------------------------------------------------------------------
# Where the picture comes from: this film, or the shared shelf
# --------------------------------------------------------------------------

def picture(path, w, h):
    """A real file, because choosing between backdrops means measuring
    them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (120, 120, 120)).save(path)
    return path


def test_this_films_own_cover_folder_wins_over_the_shelf(tmp_path, shelf):
    picture(shelf / "cover" / "shared.jpg", 1600, 900)
    picture(tmp_path / "cover" / "mine.jpg", 1600, 900)
    back = choose(tmp_path, wide=True)
    assert back.name == "mine.jpg"
    assert back.shared is False


def test_with_nothing_of_its_own_a_film_takes_the_shelf(tmp_path, shelf):
    picture(shelf / "cover" / "shared.jpg", 1600, 900)
    back = choose(tmp_path, wide=True)
    assert back.name == "shared.jpg"
    assert back.shared is True


def test_a_wide_film_takes_the_wide_picture(tmp_path, shelf):
    picture(shelf / "cover" / "a_tall.jpg", 900, 1600)
    picture(shelf / "cover" / "b_wide.jpg", 1600, 900)
    assert choose(tmp_path, wide=True).name == "b_wide.jpg"


def test_a_vertical_film_takes_the_tall_picture(tmp_path, shelf):
    """Alphabetically first is the wide one, so this can only pass by
    measuring the pictures rather than sorting them."""
    picture(shelf / "cover" / "a_wide.jpg", 1600, 900)
    picture(shelf / "cover" / "b_tall.jpg", 900, 1600)
    assert choose(tmp_path, wide=False).name == "b_tall.jpg"


def test_one_picture_on_the_shelf_is_used_for_both_shapes(tmp_path, shelf):
    """Cropped, not letterboxed. Half a setup still beats no cover."""
    picture(shelf / "cover" / "only.jpg", 1600, 900)
    assert choose(tmp_path, wide=False).name == "only.jpg"
    assert choose(tmp_path, wide=True).name == "only.jpg"


def test_an_empty_shelf_and_an_empty_project_is_not_an_error(tmp_path, shelf):
    assert choose(tmp_path, wide=True).path is None


def test_a_square_picture_counts_as_wide(tmp_path, shelf):
    """It has to count as something, and a 16:9 crop of a square loses
    less than a 9:16 crop of one."""
    assert library.is_wide(picture(shelf / "cover" / "sq.jpg", 800, 800))


def test_something_that_is_not_a_picture_is_not_mistaken_for_one(tmp_path,
                                                                 shelf):
    """A .jpg that is not a jpg. It must not be reported as a shape."""
    (shelf / "cover" / "broken.jpg").write_bytes(b"not a picture")
    assert library.is_wide(shelf / "cover" / "broken.jpg") is None


# --------------------------------------------------------------------------
# The words
# --------------------------------------------------------------------------

def mine(path):
    return Backdrop(path, shared=False)


def test_an_explicit_title_beats_everything(tmp_path):
    img = tmp_path / "Zima nad morzem.jpg"
    (tmp_path / "film.yaml").write_text("title: From the file",
                                        encoding="utf-8")
    assert title_from(mine(img), "Something else", tmp_path) == "Something else"


def test_a_title_in_film_yaml_beats_the_filename(tmp_path):
    (tmp_path / "film.yaml").write_text("title: What I Meant", encoding="utf-8")
    img = tmp_path / "Zima nad morzem.jpg"
    assert title_from(mine(img), None, tmp_path) == "What I Meant"


def test_the_filename_becomes_the_title(tmp_path):
    """Still true for a picture put in THIS film's cover/ folder: it was
    named by hand, for this film."""
    img = tmp_path / "Zima nad morzem.jpg"
    assert title_from(mine(img), None, tmp_path) == "Zima nad morzem"


def test_a_shelf_pictures_filename_is_not_the_title(tmp_path):
    """The bug this exists to stop: every film you ever make called
    "Backdrop 01", because that is what the shared picture is called."""
    shared = Backdrop(tmp_path / "backdrop_01.jpg", shared=True)
    assert title_from(shared, None, tmp_path) == cover.title_of(tmp_path)


def test_with_no_picture_at_all_the_film_is_called_after_its_folder(tmp_path):
    """A project called my_first_film is a film called "My First Film",
    not a variable name."""
    assert title_from(Backdrop(), None, tmp_path) == cover.title_of(tmp_path)


def test_underscores_in_a_folder_name_become_a_title():
    assert cover.pretty_name("late_evening_walk") == "Late Evening Walk"


def test_an_empty_title_is_respected_not_replaced(tmp_path):
    """--title "" means you want the picture on its own."""
    assert title_from(mine(tmp_path / "x.jpg"), "", tmp_path) == ""


def test_an_unreadable_film_yaml_does_not_stop_the_cover(tmp_path):
    """Mid-edit, film.yaml is often not valid YAML. A thumbnail is not
    the thing that should break over it."""
    (tmp_path / "film.yaml").write_text("title: [unclosed", encoding="utf-8")
    assert title_from(Backdrop(), None, tmp_path) == cover.title_of(tmp_path)


# --------------------------------------------------------------------------
# When it gets rebuilt
# --------------------------------------------------------------------------

def test_a_film_with_no_thumbnail_needs_one(tmp_path):
    assert is_stale(tmp_path)


def test_a_thumbnail_older_than_the_film_is_rebuilt(tmp_path):
    """A title that no longer matches the film is worse than no title."""
    import os
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "cover.jpg").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text("fps: 24", encoding="utf-8")
    os.utime(tmp_path / "out" / "cover.jpg", (1, 1))
    assert is_stale(tmp_path)


def test_a_thumbnail_newer_than_the_film_is_left_alone(tmp_path):
    """This is what protects one you made by hand with --title from being
    quietly replaced the next time you render."""
    import os
    (tmp_path / "out").mkdir()
    (tmp_path / "film.yaml").write_text("fps: 24", encoding="utf-8")
    (tmp_path / "out" / "cover.jpg").write_bytes(b"x")
    os.utime(tmp_path / "film.yaml", (1, 1))
    assert not is_stale(tmp_path)


# --------------------------------------------------------------------------
# Setting the title
# --------------------------------------------------------------------------

def test_a_short_title_is_set_large():
    font, lines = layout_title(draw(), "Zima", 1080, 1920, None)
    assert lines == ["Zima"]
    assert font.size > 1920 * 0.10


def test_a_long_title_is_set_smaller_rather_than_running_off_the_edge():
    short, _ = layout_title(draw(), "Zima", 1080, 1920, None)
    long, _ = layout_title(
        draw(), "This is where my grandfather used to work every morning",
        1080, 1920, None)
    assert long.size < short.size


def test_the_title_never_takes_more_lines_than_it_may():
    _, lines = layout_title(
        draw(), "This is where my grandfather used to work every single "
        "morning before dawn and long after dark", 1080, 1920, None)
    assert len(lines) <= TITLE_MAX_LINES


def test_the_title_never_eats_the_picture():
    """The bug this constant exists for: sized on width alone, the
    biggest type that fits three lines is one word per line filling the
    whole frame -- a ransom note, not a cover."""
    d = draw()
    from ffilm.render import line_height
    for text in ("Zima", "Zima nad morzem", "Zima nad morzem w Kolobrzegu"):
        font, lines = layout_title(d, text, 1080, 1920, None)
        lh = line_height(font)
        block = int(lh * cover.TITLE_LINE_SPACING) * (len(lines) - 1) + lh
        assert block <= 1920 * TITLE_MAX_BLOCK + 1, text


def test_every_line_fits_across_the_frame():
    d = draw()
    font, lines = layout_title(d, "Zima nad morzem w Kolobrzegu", 1080, 1920,
                               None)
    for ln in lines:
        assert d.textlength(ln, font=font) <= 1080 * TITLE_MAX_WIDTH + 1


def test_one_unbreakably_long_word_does_not_hang_the_sizer():
    font, lines = layout_title(draw(), "A" * 300, 1080, 1920, None)
    assert font.size >= 14
    assert lines


# --------------------------------------------------------------------------
# Keeping white type readable over a bright photograph
# --------------------------------------------------------------------------

def test_the_band_behind_the_title_is_darkened():
    out = scrim(photo(400, 800), top=600, bottom=760)
    assert out[700].mean() < 200


def test_the_top_of_the_picture_is_left_alone():
    out = scrim(photo(400, 800), top=600, bottom=760)
    assert out[0].mean() == 200


def test_the_darkening_arrives_gradually_rather_than_as_an_edge():
    out = scrim(photo(400, 800), top=600, bottom=760)
    rows = [out[y].mean() for y in range(480, 600, 10)]
    assert rows == sorted(rows, reverse=True)


# --------------------------------------------------------------------------
# The file itself
# --------------------------------------------------------------------------

def test_the_cover_is_small_enough_to_actually_upload(tmp_path):
    """YouTube rejects anything over 2MB, and finding that out from a web
    form after the render and the upload is a bad moment."""
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (1920, 1080, 3), dtype=np.uint8)
    out = tmp_path / "cover.jpg"
    assert save(noise, out) <= MAX_BYTES
    assert out.exists()


def test_an_ordinary_cover_is_not_needlessly_degraded(tmp_path):
    """The quality ladder is a rescue, not a policy -- a picture that is
    already small enough must come out at full quality."""
    out = tmp_path / "cover.jpg"
    save(photo(1080, 1920), out)
    assert out.stat().st_size < MAX_BYTES
