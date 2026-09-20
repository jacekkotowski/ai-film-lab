"""
Every way of recording stays on the menu.

The guide works out the next step from what is on disk, which means a
step disappears the moment the thing it produces exists. That is right
for the BEST step and wrong for the alternatives, because it makes the
whole footage path one-way: each recording is offered once, and once
you have done it -- or skipped it by pressing ENTER -- there is no
screen anywhere that offers it again.

Measured on 2026-09-20, walking a scratch project through every stage:

    media/              ENTER drag photos in  | [2] say it to the camera
    photos only         ENTER record --voice  | go | ingest
    intro + photos      ENTER record --voice  | go | ingest
    + narration         ENTER go | ingest     | [3] closing words
    + closing           ENTER go | ingest

Two holes in that. With photos in and no narration yet there is no way
to talk to the camera at all -- which is what Jacek hit: he pressed
ENTER meaning to record an intro, got the narration window, and no
later screen would take him back. And once a narration exists, saying
it again is never offered, although `kinds.pick_narration` has taken
the newest one since 2026-09-18 and re-recording is exactly how anybody
says "not that one, this one".

So the doors are appended to every menu that does not already hold
them, last, after the alternatives that are actually next.
"""

import os
from pathlib import Path

from ffilm.guide import next_steps, recording_doors


def at(root: Path, rel: str, t: float, text: str = "x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    os.utime(p, (t, t))


def shapes(steps):
    """The command of each step, without `-p NAME`."""
    out = []
    for s in steps:
        args = []
        for a in s.args:
            if a == "-p":
                break
            args.append(a)
        out.append(args)
    return out


# -- the two doors, as a pure function --------------------------------

def test_neither_door_is_offered_where_there_is_no_camera():
    assert recording_doors(["a.jpg"], [], windows=False) == []


def test_the_camera_is_offered_to_anything_that_has_material():
    doors = shapes(recording_doors(["a.jpg"], [], windows=True))
    assert ["record"] in doors


def test_the_narration_is_offered_wherever_there_are_pictures():
    doors = shapes(recording_doors(["a.jpg"], [], windows=True))
    assert ["record", "--voice"] in doors


def test_a_film_with_no_pictures_is_not_offered_a_narration():
    doors = shapes(recording_doors(["rec_20260920-1400.mp4"], [],
                                   windows=True))
    assert ["record", "--voice"] not in doors
    assert ["record"] in doors


def test_a_door_already_on_the_menu_is_not_offered_twice():
    doors = shapes(recording_doors(["a.jpg"], [["record", "--voice"]],
                                   windows=True))
    assert ["record", "--voice"] not in doors
    assert ["record"] in doors


def test_the_narration_door_says_the_newest_one_wins():
    door = [d for d in recording_doors(["a.jpg"], [], windows=True)
            if d.args[:2] == ["record", "--voice"]][0]
    assert "newest" in door.why.lower()


# -- the stages Jacek actually walked ---------------------------------

def test_photos_with_no_narration_can_still_reach_the_camera(tmp_path):
    """The one he hit: ENTER opened the narration window, and nothing
    on any screen afterwards would record an intro."""
    at(tmp_path, "media/1_xray.jpg", 100)
    steps = next_steps(tmp_path)
    assert shapes(steps)[0] == ["record", "--voice"]     # still the best
    assert ["record"] in shapes(steps)                   # and now reachable


def test_a_narration_you_are_not_happy_with_can_be_said_again(tmp_path):
    at(tmp_path, "media/1_xray.jpg", 100)
    at(tmp_path, "media/voiceover_20260920-142000.wav", 200)
    assert ["record", "--voice"] in shapes(next_steps(tmp_path))


def test_a_finished_film_can_still_go_back_to_the_camera(tmp_path):
    at(tmp_path, "media/1_xray.jpg", 100)
    at(tmp_path, "media/voiceover_20260920-142000.wav", 200)
    at(tmp_path, "media/rec_20260920-1430.mp4", 300)
    shp = shapes(next_steps(tmp_path))
    assert ["record"] in shp
    assert ["record", "--voice"] in shp


def test_the_doors_never_take_the_place_of_the_real_next_step(tmp_path):
    """Appended, not promoted: the best step and the alternatives that
    are genuinely next keep their places."""
    at(tmp_path, "media/1_xray.jpg", 100)
    at(tmp_path, "media/voiceover_20260920-142000.wav", 200)
    shp = shapes(next_steps(tmp_path))
    assert shp[0] == ["go"]
    assert shp.index(["record", "--voice"]) > shp.index(["ingest"])
