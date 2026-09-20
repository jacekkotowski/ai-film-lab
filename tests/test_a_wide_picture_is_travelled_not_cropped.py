"""
A picture wider than the frame is travelled, not cropped.

A vertical film is 1080x1920. Drop a 600x260 picture into it and the
crop window at scale 1.0 is only 0.24 of the picture's width: three
quarters of it is never on screen at all. `pan_*` travels PAN (0.13) of
the width and `drift_*` travels DRIFT (0.045), both measured against the
picture -- so on a picture four times too wide, the widest move in the
set still shows about a third of it and the default shows a tenth.

Found 2026-09-20 on 1930s Austria Had Photoshop, picture 5: three
versions of the same photograph side by side, and the narration names
them "on the left... in the middle and on the right". The move was
`drift_right`. Jacek: "they do some panning but it is insufficient".

So: when the window cannot show most of the picture, the shot gets an
explicit sweep across it, and the direction is the one that ENDS on the
focus point ingest found -- which keeps the existing rule that a move
travels towards the thing worth looking at.

Pure: numbers in, two cx values out. No files.
"""

from ffilm.scaffold import SWEEP_BELOW, sweep_across

VERTICAL = (1080, 1920)


def test_the_triptych_that_started_this_is_swept_end_to_end():
    # 600x260, focus on the right-hand panel. Window is 0.244 of the
    # width, so a full sweep runs 0.12..0.88 less the edge margin.
    a, b = sweep_across(600, 260, *VERTICAL, focus_x=0.812)
    assert a < b                                  # left to right
    assert 0.10 < a < 0.18
    assert 0.82 < b < 0.90
    assert b - a > 0.6                            # most of the picture


def test_it_ends_on_the_side_the_focus_point_is():
    left = sweep_across(600, 260, *VERTICAL, focus_x=0.15)
    right = sweep_across(600, 260, *VERTICAL, focus_x=0.85)
    assert left[0] > left[1]                      # right to left
    assert right[0] < right[1]                    # left to right
    assert sorted(left) == sorted(right)          # same ground covered


def test_a_tall_picture_is_left_alone():
    # 1024x1536 in a vertical frame: the window already shows 84% of the
    # width. Nothing worth travelling, and a sweep would only wobble.
    assert sweep_across(1024, 1536, *VERTICAL, focus_x=0.71) is None


def test_a_picture_the_shape_of_the_frame_is_left_alone():
    assert sweep_across(1080, 1920, *VERTICAL, focus_x=0.5) is None


def test_the_threshold_is_where_it_says_it_is():
    # Just inside and just outside SWEEP_BELOW of the width.
    frame = 1080 / 1920
    narrow = frame / (SWEEP_BELOW - 0.05)       # window shows less -> sweep
    wide = frame / (SWEEP_BELOW + 0.05)         # window shows more -> leave
    assert sweep_across(1000, int(1000 / narrow), *VERTICAL, 0.9) is not None
    assert sweep_across(1000, int(1000 / wide), *VERTICAL, 0.9) is None


def test_a_sweep_never_leaves_the_picture():
    for w, h in ((600, 260), (4000, 300), (1200, 900)):
        got = sweep_across(w, h, *VERTICAL, focus_x=0.9)
        if got is None:
            continue
        half = (1080 / 1920) / (w / h) / 2
        for cx in got:
            assert half <= cx <= 1 - half, (w, h, cx)


def test_a_wide_frame_asks_less_of_a_wide_picture():
    """The same picture in a 1920x1080 film: the window is much wider, so
    there is less to travel -- and below the threshold, nothing."""
    assert sweep_across(600, 260, 1920, 1080, focus_x=0.812) is not None
    assert sweep_across(1200, 900, 1920, 1080, focus_x=0.812) is None
