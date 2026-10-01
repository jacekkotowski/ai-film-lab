"""
A slide of two columns is found without being told.

2026-10-01, Excel Tutorial - Use tables: seven PNGs of 2160x1920, each
two columns that are exactly the vertical frame's own shape side by
side. No menu and no model: a picture twice as wide as the frame is
two frames, and `columns` shows them one after the other.

Pure: sizes in, yes/no out. No files.
"""

from ffilm.scaffold import is_two_columns

VERTICAL = (1080, 1920)


def test_the_excel_slides_are_two_columns():
    assert is_two_columns(2160, 1920, *VERTICAL)


def test_it_is_the_proportion_that_counts_not_the_pixels():
    assert is_two_columns(1080, 960, *VERTICAL)       # half the size
    assert is_two_columns(4320, 3840, *VERTICAL)      # double the size
    assert is_two_columns(1620, 1440, *VERTICAL)
    assert is_two_columns(2160, 1920, 720, 1280)      # another 9:16 frame


def test_a_few_pixels_off_is_still_two_columns():
    assert is_two_columns(2150, 1920, *VERTICAL)      # a trimmed export


def test_a_ordinary_wide_or_square_picture_is_not():
    assert not is_two_columns(1920, 1080, *VERTICAL)  # 16:9 photograph
    assert not is_two_columns(1024, 1536, *VERTICAL)  # a labelled diagram
    assert not is_two_columns(1080, 1080, *VERTICAL)  # square
    assert not is_two_columns(600, 260, *VERTICAL)    # the triptych


def test_nothing_is_found_in_a_picture_with_no_size():
    assert not is_two_columns(0, 0, *VERTICAL)


# --- one table across both halves is panned slowly, not held in turn -------
#
# Jacek, 2026-10-01: "if the slide is just a big table twice the width then
# I would like a slow panning ... visibly two areas vs one spanning across."
# Measured on the seven real slides: the only thing in the gutter is the
# divider and a connector arrow, 4.8% of the rows at most.

import numpy as np

from ffilm.scaffold import spans_the_middle


def _slide(w=2160, h=1920):
    img = np.full((h, w, 3), (14, 20, 22), np.uint8)
    img[:, w // 2 - 1:w // 2 + 1:] = (60, 60, 60)       # the divider
    return img


def test_two_areas_with_an_arrow_between_them_do_not_span():
    img = _slide()
    img[200:900, 100:1000] = 240                         # left panel
    img[200:900, 1160:2060] = 240                        # right panel
    img[917:1003, 990:1170] = (27, 127, 71)              # connector arrow
    assert not spans_the_middle(img)


def test_a_table_running_across_the_middle_spans():
    img = _slide()
    img[400:1400, 100:2060] = 240                        # one wide table
    assert spans_the_middle(img)


def test_an_empty_slide_does_not_span():
    assert not spans_the_middle(_slide())


def test_it_does_not_matter_how_big_the_slide_is():
    img = _slide(1080, 960)
    img[200:700, 50:1030] = 240
    assert spans_the_middle(img)
