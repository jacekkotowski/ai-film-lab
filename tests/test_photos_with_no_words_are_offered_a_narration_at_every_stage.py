"""
Photos with no words over them are offered a narration at every stage.

Found 2026-09-18 by walking the guide through Jacek's plan -- talk to the
camera, then say a few words over some slides. The guide's first offer
is "Build the whole film in one go", and `go` renders a draft. The offer
to "say the words over these pictures" lived only in the branch for a
film nobody had rendered yet, so taking the guide's own advice made it
vanish: the next screen said "Ship it" over silent slides.

Now it is on offer until the pictures have a narration: first while
nothing has been rendered (narrating is why you would stop there), and
right after the main step once something has (a slideshow meant to run
under music should still be able to ship with ENTER).

The other half of the same walk: a project holding only a camera take
was sent straight to "Build the whole film", with no word that photos
to narrate go in first. It now says so, as an alternative.

Pure: files with set modification times in a temporary folder.
"""

import os
from pathlib import Path

from ffilm.guide import next_steps

PHOTO_AND_CLIP = ('{"path": "media/a.jpg", "kind": "still"}, '
                  '{"path": "media/b.mp4", "kind": "video", '
                  '"sound": {"has": true, "ratio": 0.5}}')


def at(root: Path, rel: str, t: float, text: str = "x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    os.utime(p, (t, t))


def edited(tmp_path: Path, yml: str = "shots: []\n", **renders) -> Path:
    """Photos and a talking clip, ingested at 200, edited at 300."""
    at(tmp_path, "media/a.jpg", 100)
    at(tmp_path, "media/b.mp4", 100)
    at(tmp_path, "analysis/manifest.json", 200,
       '{"count": 2, "unreadable": [], "media": [' + PHOTO_AND_CLIP + ']}')
    at(tmp_path, "film.yaml", 300, yml)
    for name, t in renders.items():
        at(tmp_path, f"out/{name}.mp4", t)
    return tmp_path


def narrate_at(root: Path) -> int | None:
    for i, s in enumerate(next_steps(root)):
        if s.args[:2] == ["record", "--voice"]:
            return i
    return None


def test_it_is_the_first_thing_offered_before_anything_is_rendered(tmp_path):
    assert narrate_at(edited(tmp_path)) == 0


def test_it_survives_the_draft_that_go_renders(tmp_path):
    assert narrate_at(edited(tmp_path, draft=400)) == 1


def test_it_survives_a_peek_and_a_draft(tmp_path):
    assert narrate_at(edited(tmp_path, peek=400, draft=500)) == 1


def test_it_stops_leading_once_the_pictures_carry_a_narration(tmp_path):
    """It used to vanish outright. Since 2026-09-20 it stays on as the
    last thing on the menu -- the standing door -- because a narration
    you are not happy with is re-recorded, and the guide offered no way
    at all to do that. What it must not be any more is near the top."""
    slides = ("shots:\n  - src: media/a.jpg\n"
              "    voice: media/voiceover_1.wav\n    in: 0\n    out: 5\n")
    for n, renders in enumerate(({}, {"draft": 400})):
        root = edited(tmp_path / f"r{n}", yml=slides, **renders)
        steps = next_steps(root)
        i = narrate_at(root)
        assert i == len(steps) - 1
        assert steps[i].title.endswith("again")


def test_a_camera_take_alone_is_told_photos_can_go_in_first(tmp_path):
    at(tmp_path, "media/rec_20260918-101500.mp4", 100)
    steps = next_steps(tmp_path)
    assert steps[0].args[0] == "go"
    photos = [s for s in steps if "photos" in s.title.lower()]
    assert photos and photos[0].folders[0].name == "media"


def test_photos_already_in_are_not_asked_for_again(tmp_path):
    at(tmp_path, "media/rec_20260918-101500.mp4", 100)
    at(tmp_path, "media/a.jpg", 100)
    assert not any("photos" in s.title.lower() for s in next_steps(tmp_path))
