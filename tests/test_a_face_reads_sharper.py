"""
A face in a vertical film, sharpened before the camera move.

A 9:16 crop of a 1920x1080 take keeps 607 pixels of width and enlarges
them 1.78x, so the face is soft from the enlargement, not from the
camera. Measured on "I am not your fear" at 1:00, Laplacian variance of
the face at output size: plain 7.1, sharpened before the warp 9.9,
smoothed before the warp 3.5. Smoothing was refused for that reason:
the grain would paint texture back onto mush.

It happens on the SOURCE frame, before the warp and long before the look
(grade, vignette, grain, scratches), which it does not touch. Recordings
only: a photograph or somebody else's clip is left as it was made.
"""

import numpy as np

from ffilm import render
from ffilm.spec import Film, Shot


def edge(w=64, h=64):
    img = np.full((h, w, 3), 100, dtype=np.uint8)
    img[:, w // 2:] = 160
    return img


def contrast_at_edge(img):
    row = img[32, :, 0].astype(int)
    return row.max() - row.min()


def test_no_sharpening_returns_the_frame_untouched():
    img = edge()
    assert render.sharpen(img, 0.0) is img


def test_sharpening_makes_an_edge_crisper():
    assert contrast_at_edge(render.sharpen(edge(), 0.35)) > contrast_at_edge(edge())


def test_a_flat_area_is_left_flat():
    """Unsharp masking only moves what differs from its surroundings --
    a flat wall gets no new texture for the grain to fight with."""
    flat = np.full((64, 64, 3), 120, dtype=np.uint8)
    assert np.array_equal(render.sharpen(flat, 0.35), flat)


def test_only_where_the_person_is_when_there_is_a_mask():
    """With bokeh on, the room is blurred on purpose. Sharpening it back
    would undo the blur."""
    mask = np.zeros((8, 8), dtype=np.float32)          # nobody anywhere
    img = edge()
    assert np.array_equal(render.sharpen(img, 0.35, mask), img)


def test_only_recordings_are_sharpened():
    film = Film()
    take = Shot(src="media/rec_20260916-113221.mp4", kind="video")
    clip = Shot(src="media/harbour.mp4", kind="video")
    still = Shot(src="media/rec_photo.jpg", kind="still")
    assert render.sharpen_for(film, take) == render.SHARPEN
    assert render.sharpen_for(film, clip) == 0.0
    assert render.sharpen_for(film, still) == 0.0


def test_the_look_is_not_touched():
    """The projector look is liked and stays exactly as it is."""
    import inspect
    assert "sharpen" not in inspect.getsource(render.apply_look)
