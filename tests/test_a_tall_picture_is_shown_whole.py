"""
A tall picture is shown whole.

Found 2026-09-23: a 361x811 photograph in a vertical film was cropped to
at most 79% of its height, and the equipment in it never seen whole.
Such a picture now rises from its bottom edge to its top edge.
"""

from ffilm.moves import SETTLE, windows_for
from ffilm.spec import Shot


def test_rise_travels_from_the_bottom_edge_to_the_top_edge():
    s = Shot.parse({"src": "media/tall.jpg", "move": "rise",
                    "duration": 5.0}, 0)
    f, t = windows_for(s)
    assert f.cy >= 1.0 and f.scale == 1.0             # starts at the bottom
    assert abs(f.cy + (t.cy - f.cy) * SETTLE) < 1e-9  # reaches the very top
    assert t.scale == 1.0                             # never zooms in
