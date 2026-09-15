"""
Bokeh -- the room behind you blurs, and you stay sharp.

Not `fill: blur`, which blurs a copy of the WHOLE picture around it. This
keeps the frame as it is and softens only what is not the person, using a
small segmentation model that is fetched once into models/ and never
committed (see models/README.md).

Measured before it was built, on "I love you" (240 frames at 1:00):
MediaPipe's landscape selfie model 10.8 ms a frame, and it blurred the
door and the hanger that PP-HumanSeg took for a second person.
"""

import re
import numpy as np
import cv2
from ffilm import segment
from ffilm.paths import toolkit_root
from ffilm.spec import Film, Shot


def room(w=640, h=360):
    """Stripes everywhere, so blur is measurable anywhere in the frame."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, ::8] = 255
    return img


def half_mask(h=36, w=64):
    """The person is the left half. The model's mask is small; bokeh
    enlarges it to the frame."""
    m = np.zeros((h, w), dtype=np.float32)
    m[:, : w // 2] = 1.0
    return m


def test_where_the_person_is_the_picture_is_untouched():
    out = segment.bokeh(room(), half_mask(), 1.0)
    assert np.array_equal(out[:, :300], room()[:, :300])


def test_where_the_room_is_it_is_blurred():
    out = segment.bokeh(room(), half_mask(), 1.0)
    assert out[:, 340:].std() < 0.5 * room()[:, 340:].std()


def test_strength_zero_changes_nothing():
    assert np.array_equal(segment.bokeh(room(), half_mask(), 0.0), room())


def test_more_strength_is_softer():
    """Wide stripes: fine ones are already flat at strength 1."""
    wide = np.zeros((360, 640, 3), dtype=np.uint8)
    wide[:, 160:320] = 255
    wide[:, 480:] = 255
    soft = segment.bokeh(wide, np.zeros((36, 64), np.float32), 1.0)
    softer = segment.bokeh(wide, np.zeros((36, 64), np.float32), 2.0)
    assert softer.std() < soft.std()


def test_the_edge_is_steadied_over_frames():
    """Measured: averaging each mask with the last halved the edge
    shimmer (0.055 -> 0.029). The first frame has nothing to average."""
    s = segment.MaskSmoother()
    a = np.ones((4, 4), np.float32)
    b = np.zeros((4, 4), np.float32)
    assert np.array_equal(s.smooth(a), a)
    assert np.allclose(s.smooth(b), 0.5)


def test_a_film_has_no_bokeh_unless_it_asks():
    assert Film().bokeh == 0.0


def test_a_shot_can_turn_it_on_or_off_for_itself():
    film = Film(bokeh=1.0)
    plain = Shot.parse({"src": "a.mp4", "out": 2}, 0)
    off = Shot.parse({"src": "a.mp4", "out": 2, "bokeh": 0}, 1)
    stronger = Shot.parse({"src": "a.mp4", "out": 2, "bokeh": 1.5}, 2)
    assert film.bokeh_for(plain) == 1.0
    assert film.bokeh_for(off) == 0.0
    assert film.bokeh_for(stronger) == 1.5


def test_photographs_are_left_alone():
    """Asked for on recorded takes. A photograph has no next frame to
    steady the edge with."""
    film = Film(bokeh=1.0)
    assert film.bokeh_for(Shot.parse({"src": "a.jpg"}, 0)) == 0.0


def test_a_missing_model_is_said_not_skipped(tmp_path):
    """Face detection once died silently and nobody noticed for weeks
    (docs/decisions/0001). A film that asks for bokeh without the model
    is told where to get it."""
    msg = segment.missing_model(tmp_path)
    assert msg and segment.MODEL_FILE in msg and segment.MODEL_URL in msg
    (tmp_path / segment.MODEL_FILE).write_bytes(b"x")
    assert segment.missing_model(tmp_path) is None


def test_the_url_in_the_code_is_the_one_in_the_readme():
    readme = (toolkit_root() / "models" / "README.md").read_text(encoding="utf-8")
    assert segment.MODEL_URL in re.findall(r"https://\S+", readme)
