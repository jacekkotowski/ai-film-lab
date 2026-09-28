"""
`film check` says which photographs get parallax, and whether it can
happen on this computer -- before the render, not half way into it.
A film that asks for depth and cannot have it renders flat and must say
so, the way a missing bokeh model does.
"""

from ffilm.checks import depth_notes
from ffilm.spec import Film, Shot


def film(**kw):
    return Film(shots=[Shot.parse({"src": "media/a.jpg", "id": "s01"}, 0),
                       Shot.parse({"src": "media/chart.png", "id": "s02",
                                   "depth": 0}, 1),
                       Shot.parse({"src": "media/rec_1.mp4", "out": 2,
                                   "id": "s03"}, 2)], **kw)


def test_nothing_is_said_when_nothing_asks():
    assert depth_notes(film(), runner=None, model_present=True) == []


def test_it_names_the_shots_that_get_depth():
    notes = depth_notes(film(depth=0.5), runner=None, model_present=True)
    text = "\n".join(notes)
    assert "s01" in text and "s02" not in text and "s03" not in text


def test_without_the_runner_it_says_how_to_get_it():
    notes = depth_notes(film(depth=0.5), runner="needs onnxruntime: "
                        "uv sync --extra depth", model_present=True)
    assert any("uv sync --extra depth" in n for n in notes)
    assert any("flat" in n for n in notes)


def test_without_the_model_it_says_it_will_download():
    notes = depth_notes(film(depth=0.5), runner=None, model_present=False)
    assert any("depth_anything_v2_small.onnx" in n for n in notes)
