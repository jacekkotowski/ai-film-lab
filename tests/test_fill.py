"""
Blurred fill -- the picture whole, on a blurred copy of itself.

The case it exists for: a 16:9 webcam in a 9:16 film. Cropping to fill
keeps 32% of the width, which takes both ears off somebody sitting close
to the camera. Showing ALL of the picture instead is not the answer
either -- it leaves the speaker a fifth of the frame tall, solving the
crop by making them too small to see. So a squarer piece of the picture
sits sharp on a blurred enlargement of the rest.
"""

import numpy as np
import cv2
from ffilm.render import blurred_fill, compose, warp
from ffilm.spec import Film, Shot, Window


def scene(w=1280, h=720):
    """A picture with a bright band down the middle, so it is obvious
    which part of it ended up where."""
    img = np.full((h, w, 3), 40, dtype=np.uint8)
    img[:, w // 2 - 60:w // 2 + 60] = 240
    return img


WIN = Window(0.5, 0.5, 1.0, 0.0)


def test_the_output_is_still_exactly_the_frame_asked_for():
    out = blurred_fill(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, 1.0)
    assert out.shape[:2] == (1920, 1080)


def test_the_sharp_part_is_the_shape_you_asked_for():
    out = blurred_fill(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, 1.0)
    band = warp(scene(), WIN, 1080, 1080, cv2.INTER_LINEAR)
    assert np.array_equal(out[420:1500], band)


def test_a_taller_sharp_part_leaves_less_blur():
    """fill_aspect 0.8 is 4:5 -- bigger subject, narrower crop."""
    out = blurred_fill(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, 0.8)
    assert np.array_equal(out[285:1635],
                          warp(scene(), WIN, 1080, 1350, cv2.INTER_LINEAR))


def test_the_background_is_knocked_back_not_left_competing():
    out = blurred_fill(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, 1.0)
    plain = warp(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR)
    assert out[:400].mean() < plain[:400].mean()


def test_the_background_is_actually_blurred():
    """Not black bars: the room is still there, softly."""
    out = blurred_fill(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, 1.0)
    assert out[:400].std() < warp(scene(), WIN, 1080, 1920,
                                  cv2.INTER_LINEAR)[:400].std()
    assert out[:400].mean() > 1        # and not simply painted out


def test_asking_for_blur_where_none_could_show_just_crops():
    """A square sharp part in a 16:9 frame is taller than the frame. A
    plain crop beats a one-pixel halo."""
    out = blurred_fill(scene(), WIN, 1920, 1080, cv2.INTER_LINEAR, 1.0)
    assert np.array_equal(out, warp(scene(), WIN, 1920, 1080,
                                    cv2.INTER_LINEAR))


def test_every_film_that_never_asked_for_this_is_untouched():
    film = Film()
    shot = Shot(src="a.mp4", kind="video", duration=5.0, id="s01")
    assert film.fill == "crop"
    out = compose(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, film, shot)
    assert np.array_equal(out, warp(scene(), WIN, 1080, 1920,
                                    cv2.INTER_LINEAR))


def test_one_shot_can_disagree_with_the_film():
    """A photograph crops happily; the clip of a face beside it does not."""
    film = Film(fill="blur")
    photo = Shot(src="a.jpg", kind="still", duration=5.0, id="s01",
                 fill="crop")
    out = compose(scene(), WIN, 1080, 1920, cv2.INTER_LINEAR, film, photo)
    assert np.array_equal(out, warp(scene(), WIN, 1080, 1920,
                                    cv2.INTER_LINEAR))


# --------------------------------------------------------------------------
# A clip must never be memoised
# --------------------------------------------------------------------------

def test_a_photograph_may_reuse_its_rendered_frame():
    """A still under a still camera is the same warp 480 times over."""
    from ffilm.render import should_memoise
    assert should_memoise(Shot(src="a.jpg", kind="still", duration=5, id="s"))


def test_a_clip_may_never_reuse_its_rendered_frame():
    """THE freeze. A clip's picture changes 25 times a second on its own,
    so reusing a frame stops the picture while the grain and scratches
    carry on animating over the top -- which reads as a broken filter
    rather than a stopped image. It stayed hidden until `static` became
    the right move for a talking head, being the only move whose window
    does not change from frame to frame."""
    from ffilm.render import should_memoise
    for move in ("static", "drift_left", "push_in"):
        shot = Shot(src="a.mp4", kind="video", duration=5, move=move, id="s")
        assert not should_memoise(shot), move
