"""
Anything the vertical frame would crop is travelled, not lost.

A vertical film is 1080x1920. The crop window at scale 1.0 has the
frame's shape and is as large as fits inside the picture, so on any
picture relatively wider than the frame it is height-limited and shows
`frame_aspect / src_aspect` of the width. Whatever is left is off
screen for the whole shot.

Two sizes from 1930s Austria Had Photoshop, 2026-09-20:

    600x260   triptych   window 0.24 of the width  -- 76% never seen
    1024x1536 diagram    window 0.84 of the width  -- 16% never seen

The first was obvious: three photographs side by side, narrated "on the
left... in the middle and on the right", with `move: drift_right`, which
travels DRIFT (0.045) of the width. Jacek: "they do some panning but it
is insufficient".

The second is the one that matters more, and the first version of this
rule missed it by setting the threshold at 0.80. Those diagrams carry a
column of labels down the right-hand edge -- "Glass plate (top)",
"Positive mask", "Original negative" -- and 16% of the width is exactly
that column. Jacek: "in the case of visuals you cut the captions on the
right of the images". So the threshold is now "anything at all".

Direction is always left to right. It used to be the side the focus
point sat on, which is right on a photograph and wrong on a diagram:
the cropped part is the labels on the right, and you want to arrive
there, in reading order.

Pure: numbers in, two cx values out. No files.
"""

from ffilm.scaffold import MIN_SWEEP, sweep_across

VERTICAL = (1080, 1920)
WIDE = (1920, 1080)


def test_the_triptych_is_swept_end_to_end():
    a, b = sweep_across(600, 260, *VERTICAL)
    assert a < b
    assert b - a > 0.6                      # most of the picture


def test_the_labelled_diagram_that_the_first_threshold_missed():
    """1024x1536: only 16% is cropped, and all of it is the labels."""
    got = sweep_across(1024, 1536, *VERTICAL)
    assert got is not None
    a, b = got
    assert a < b
    # It cannot reveal more than was hidden, and should reveal most of it.
    hidden = 1 - (1080 / 1920) / (1024 / 1536)
    assert 0.8 * hidden - 1e-9 <= b - a <= hidden + 1e-9


def test_it_always_goes_left_to_right():
    for w, h in ((600, 260), (1024, 1536), (4000, 300)):
        a, b = sweep_across(w, h, *VERTICAL)
        assert a < b, (w, h)


def test_a_picture_the_shape_of_the_frame_is_left_alone():
    assert sweep_across(1080, 1920, *VERTICAL) is None


def test_a_picture_taller_than_the_frame_is_left_alone():
    """Nothing is cropped off the sides, so there is nothing to travel."""
    assert sweep_across(1080, 2400, *VERTICAL) is None


def test_a_sliver_too_wide_is_not_worth_a_wobble():
    # Cropped by well under MIN_SWEEP of the width.
    assert sweep_across(1000, 1760, *VERTICAL) is None


def test_a_sweep_never_leaves_the_picture():
    for w, h in ((600, 260), (4000, 300), (1024, 1536), (1200, 1500)):
        got = sweep_across(w, h, *VERTICAL)
        if got is None:
            continue
        half = (1080 / 1920) / (w / h) / 2
        for cx in got:
            assert half - 1e-9 <= cx <= 1 - half + 1e-9, (w, h, cx)


def test_every_sweep_is_worth_making():
    for w, h in ((600, 260), (1024, 1536), (1200, 1500), (4000, 300)):
        got = sweep_across(w, h, *VERTICAL)
        if got is not None:
            assert got[1] - got[0] >= MIN_SWEEP


def test_the_frame_shape_is_what_decides_not_the_word_wide():
    """A 1920x1080 film crops different pictures. 1200x900 is squarer
    than that frame, so its sides survive and nothing is travelled --
    and the same 600x260 triptych is still cropped by 23%, so it is
    still swept. "Wide" is always relative to the frame."""
    assert sweep_across(1200, 900, *WIDE) is None
    got = sweep_across(600, 260, *WIDE)
    assert got is not None and got[0] < got[1]
