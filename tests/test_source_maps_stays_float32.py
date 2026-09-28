"""source_maps must give the same map, in float32, without widening its
cached grids to float64 to get there.

Measured 2026-09-28: cv2.invertAffineTransform returns float64 scalars.
`inv[0,0] * u`, with `u` the cached float32 grid, promotes the whole
1080x1920 array to float64 for that multiply, then the result is narrowed
back to float32 at the end -- twice the memory traffic for the same
numbers. Isolated benchmark (docs/decisions/0013): ~99 ms/call
before, ~41 ms/call after -- about 2.4x, on a sample outside any film.
"""

import numpy as np

from ffilm.render import source_maps, _grids
from ffilm.spec import Window


def test_the_result_stays_float32_and_the_numbers_do_not_move():
    H, W = 1968, 1523
    win = Window(cx=0.42, cy=0.5, scale=1.03)
    _grids.clear()
    mx, my = source_maps(H, W, win, 1080, 1920)
    assert mx.dtype == np.float32
    assert my.dtype == np.float32
    # Same window, computed a second way: once through cv2 alone, no
    # float32-grid shortcut, as a check that the fast path is not just
    # fast but still correct.
    import cv2
    from ffilm.render import window_affine
    M, _, _, _ = window_affine(H, W, win, 1080, 1920)
    inv = cv2.invertAffineTransform(M).astype(np.float64)
    u, v = np.meshgrid(np.arange(1080, dtype=np.float64),
                       np.arange(1920, dtype=np.float64))
    want_x = inv[0, 0] * u + inv[0, 1] * v + inv[0, 2]
    want_y = inv[1, 0] * u + inv[1, 1] * v + inv[1, 2]
    assert np.allclose(mx, want_x, atol=1e-3)
    assert np.allclose(my, want_y, atol=1e-3)
