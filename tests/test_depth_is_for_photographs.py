"""
`depth:` gives a photograph parallax: the near things slide past the far
ones as the camera moves. Film-level default, per-shot override, 0 flat.

Photographs only. A clip's picture changes 25 times a second; a depth
map made per frame flickers, and a clip already has its own parallax.
And the default is 0, so that no film already made changes under anyone.
"""

import yaml

from ffilm import editor
from ffilm.spec import Film, Shot


def test_a_film_has_no_depth_unless_it_asks():
    assert Film().depth == 0.0
    assert Film().depth_for(Shot.parse({"src": "a.jpg"}, 0)) == 0.0


def test_the_films_depth_reaches_every_photograph():
    film = Film(depth=0.5)
    assert film.depth_for(Shot.parse({"src": "media/a.jpg"}, 0)) == 0.5


def test_a_shot_can_turn_it_on_or_off_for_itself():
    film = Film(depth=0.5)
    off = Shot.parse({"src": "media/chart.png", "depth": 0}, 0)
    more = Shot.parse({"src": "media/a.jpg", "depth": 0.8}, 1)
    assert film.depth_for(off) == 0.0
    assert film.depth_for(more) == 0.8
    assert Film().depth_for(more) == 0.8


def test_clips_are_left_alone():
    film = Film(depth=0.5)
    clip = Shot.parse({"src": "media/rec_1.mp4", "out": 2, "depth": 1}, 0)
    assert film.depth_for(clip) == 0.0


def test_the_title_card_keeps_its_letters_straight():
    """The opening card is a still too -- analysis/title.jpg, the film's
    name over a photo. Parallax would bend the letters with the picture."""
    film = Film(depth=0.5)
    card = Shot.parse({"src": "analysis/title.jpg"}, 0)
    assert film.depth_for(card) == 0.0


def test_a_png_gif_or_svg_is_a_chart_and_stays_flat():
    """Jacek, 2026-09-28: charts are gif or png or svg, do not give those
    depth. Photographs are jpg/jfif; parallax bends a chart's lines."""
    film = Film(depth=0.5)
    for name in ("media/chart.png", "media/CHART.PNG", "media/a.gif",
                 "media/a.svg"):
        assert film.depth_for(Shot.parse({"src": name}, 0)) == 0.0, name
    assert film.depth_for(Shot.parse({"src": "media/a.jfif"}, 0)) == 0.5


def test_film_yaml_says_it(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text(
        "depth: 0.5\nshots:\n  - src: a.jpg\n  - src: a.jpg\n    depth: 0\n",
        encoding="utf-8")
    film = Film.load(tmp_path / "film.yaml")
    assert film.depth == 0.5
    assert [film.depth_for(s) for s in film.shots] == [0.5, 0.0]


def test_a_new_film_has_depth_on_at_half():
    """Jacek watched 0.5 to 0.8 in motion on What Is Love (2026-09-28):
    0.8 smeared, 0.5 was kept. So a new film starts with it on, at 0.5."""
    from ffilm import scaffold
    lines = scaffold.depth_lines()
    assert "depth: 0.5" in lines
    assert "# depth: 0.5" not in lines


def test_the_bench_hands_a_shots_depth_back(tmp_path):
    """The bench rewrites every shot field by field. A field it does not
    know is lost on the first Save -- as `speed` once was."""
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text(
        "depth: 0.5\nshots:\n  - src: a.jpg\n    depth: 0.8\n  - src: a.jpg\n",
        encoding="utf-8")
    text = editor.dump(tmp_path, editor.state(tmp_path))
    d = yaml.safe_load(text)
    assert d["depth"] == 0.5
    assert d["shots"][0]["depth"] == 0.8
    assert "depth" not in d["shots"][1]
