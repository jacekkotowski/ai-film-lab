"""
A narration longer than the photographs under it.

Measured on the 2026-09-17 scratch project (mixed_project.py): three
photographs at STILL_SECONDS each is 13.5s, and the 14s voiceover
recorded over them already ran past that -- `scaffold.fit_to_target`
only ever SHORTENS, so nothing in `init` grew the pictures to meet a
narration longer than they are, and the tail would have been cut with
no message (see checks.narration_note, item 1) or read wrong (item 2).

`fit_to_target` was not reused for this. Its `target` is a CEILING for
a Short -- a film already under it is left alone, however far under,
which test_a_target_that_is_already_met_changes_nothing in
test_editing_rules.py checks with a target of 300s against 18s of
stills. Growing THAT function toward a larger target would have made
that test wrong: a Shorts target and a narration's length are not the
same kind of number, one is "no more than", the other is "at least".
So this is its own function, its own floor.

Numbers only here. Nothing touches ffmpeg.
"""

from ffilm.scaffold import stretch_to_narration
from ffilm.spec import Shot


def photos(n, secs=4.5):
    shots = [Shot(src=f"media/{i}.jpg", kind="still", duration=secs,
                  id=f"s{i:02d}") for i in range(n)]
    meta = [{"entry": {"path": f"media/{i}.jpg", "kind": "still"},
             "role": None} for i in range(n)]
    return shots, meta


def total(shots):
    return sum(s.duration for s in shots)


def test_photographs_grow_to_cover_a_longer_narration():
    shots, meta = photos(3)                  # 13.5s of pictures
    stretch_to_narration(shots, meta, 20.0)
    assert total(shots) == 20.0


def test_a_narration_already_covered_changes_nothing():
    shots, meta = photos(3)                  # 13.5s of pictures
    before = [s.duration for s in shots]
    stretch_to_narration(shots, meta, 10.0)  # shorter than the pictures
    assert [s.duration for s in shots] == before


def test_growing_never_touches_a_clip():
    """The B-roll is what it filmed. Stretching it would mean slowing
    it down, which is record.REC_SPEED's decision, not a target's."""
    clip = Shot(src="media/x.mkv", kind="video", duration=6.0, id="s01")
    shots = [clip] + photos(2)[0]
    meta = [{"entry": {"path": "media/x.mkv", "kind": "video"},
             "role": None}] + photos(2)[1]
    stretch_to_narration(shots, meta, 30.0)
    assert clip.duration == 6.0


def test_growing_never_touches_speech():
    talk = Shot(src="media/x.mkv", kind="video", duration=40.0, id="s01")
    shots = [talk] + photos(2)[0]
    meta = ([{"entry": {"path": "media/x.mkv", "kind": "video"},
              "talking": True, "part": 1, "parts": 1}]
            + photos(2)[1])
    stretch_to_narration(shots, meta, 60.0)
    assert talk.duration == 40.0
    assert total(shots) == 60.0


def test_with_no_photographs_there_is_nothing_to_grow():
    talk = Shot(src="media/x.mkv", kind="video", duration=10.0, id="s01")
    shots = [talk]
    meta = [{"entry": {"path": "media/x.mkv", "kind": "video"},
             "talking": True, "part": 1, "parts": 1}]
    stretch_to_narration(shots, meta, 60.0)
    assert talk.duration == 10.0
