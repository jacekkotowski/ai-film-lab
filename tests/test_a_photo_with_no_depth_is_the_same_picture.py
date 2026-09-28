"""
`depth: 0` -- or no `depth:` at all, which is every film made before
v0.2 -- must give exactly the picture it gave before: bit for bit, on
every move. Nobody's existing film may change under them.
"""

import numpy as np
import pytest

from ffilm import render
from ffilm.moves import MOVES, window_at, window_mid
from ffilm.spec import Shot


def photo():
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, (120, 180, 3), dtype=np.uint8)


def ramp(h=120, w=180):
    return np.tile(np.linspace(0, 1, w, dtype=np.float32), (h, 1))


@pytest.mark.parametrize("move", MOVES)
def test_no_depth_is_todays_warp(move):
    shot = Shot.parse({"src": "a.jpg", "move": move, "focus": [0.4, 0.6]}, 0)
    src = photo()
    for t in (0.0, 0.3, 1.0):
        win = window_at(shot, t)
        plain = render.warp(src, win, 64, 36, render.DRAFT.interp)
        assert np.array_equal(
            render.warp_with_depth(src, win, 64, 36, render.DRAFT.interp, None),
            plain)
        flat = render.Parallax(ramp(), 0.5, window_mid(shot), strength=0.0)
        assert np.array_equal(
            render.warp_with_depth(src, win, 64, 36, render.DRAFT.interp, flat),
            plain)


def test_a_flat_depth_map_moves_nothing():
    """A chart, as far as the model can tell, is one flat thing: the same
    depth everywhere means no pixel moves against another."""
    shot = Shot.parse({"src": "a.jpg", "move": "pan_right"}, 0)
    par = render.Parallax(np.full((120, 180), 0.3, np.float32), 0.3,
                          window_mid(shot), strength=1.0)
    win = window_at(shot, 1.0)
    plain = render.source_maps(120, 180, win, 64, 36)
    moved = render.parallax_maps(120, 180, win, 64, 36, par)
    assert np.allclose(plain[0], moved[0]) and np.allclose(plain[1], moved[1])
