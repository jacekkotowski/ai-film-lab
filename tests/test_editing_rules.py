"""
The editing decisions, tested without touching a file.

Every one of these is a rule that broke in real use during the week the
toolkit was built, in front of the person using it. They are all pure
functions -- no ffmpeg, no disk, no model -- so the whole file runs in
well under a second, and there is no excuse for not running it.

    uv run --extra dev pytest
"""

from ffilm import scaffold
from ffilm.spec import Shot, parse_time


# --------------------------------------------------------------------------
# Is this a clip someone talked over, or is it B-roll?
# --------------------------------------------------------------------------


def entry(ratio, has=True, **kw):
    e = {"kind": "video", "path": "media/x.mkv", "duration": 60.0,
         "sound": {"has": has, "ratio": ratio, "in": 0.0, "out": 60.0,
                   "quiet": []}}
    e.update(kw)
    return e


def test_a_take_that_is_mostly_pauses_is_still_talking():
    """The one that actually went wrong: a 76s statement to camera measured
    0.118 audible and was thrown away as B-roll, taking twelve transcribed
    lines with it."""
    assert scaffold.is_talking(entry(0.118))


def test_barely_audible_is_broll():
    assert not scaffold.is_talking(entry(0.001))


def test_no_audio_track_at_all_is_broll():
    assert not scaffold.is_talking(entry(0.9, has=False))


def test_a_clip_with_no_sound_key_is_broll():
    """Manifests written before sound detection existed must not crash."""
    assert not scaffold.is_talking({"kind": "video", "duration": 10.0})


# --------------------------------------------------------------------------
# Keeping the words, dropping the dead air
# --------------------------------------------------------------------------


def sound(quiet, a=0.0, b=25.0):
    return {"has": True, "ratio": 0.5, "in": a, "out": b, "quiet": quiet}


def test_long_pauses_are_removed_and_every_word_is_kept():
    #  talk 0.5-4 | SILENT 4-7 | talk 7-12 | SILENT 12-16 | talk 16-24.5
    segs = scaffold.talking_segments(25.0, sound([[4.0, 7.0], [12.0, 16.0]],
                                                a=0.5, b=24.5))
    assert len(segs) == 3
    starts = [s for s, _ in segs]
    ends = [e for _, e in segs]
    assert starts[0] <= 0.5 and ends[-1] >= 24.5      # nothing at the ends lost
    for (_, e), (s, _) in zip(segs, segs[1:]):        # the gaps are the silences
        assert e < s


def test_a_short_pause_is_left_alone():
    """Speech without its breaths sounds panicked."""
    segs = scaffold.talking_segments(25.0, sound([[10.0, 10.6]]))
    assert len(segs) == 1


def test_cuts_leave_a_breath_so_words_are_not_clipped():
    segs = scaffold.talking_segments(25.0, sound([[10.0, 14.0]]))
    first_end, second_start = segs[0][1], segs[1][0]
    assert first_end > 10.0                # kept a moment past the last word
    assert second_start < 14.0             # started a moment before the next


def test_when_trimming_would_eat_the_take_it_keeps_everything():
    """A softly spoken passage reads as silence to any level threshold.
    Losing it is worse than leaving a slow patch in, so past a limit the
    detection is disbelieved."""
    greedy = [[2.0, 8.0], [10.0, 16.0], [18.0, 24.0]]     # 18 of 25 seconds
    segs = scaffold.talking_segments(25.0, sound(greedy))
    assert segs == [(0.0, 25.0)]


def test_a_take_is_never_shortened_to_fit_the_split_limit():
    long_snd = {"has": True, "ratio": 0.9, "in": 0.0, "out": 600.0,
                "quiet": [[t, t + 2.0] for t in range(100, 600, 100)]}
    segs = scaffold.talking_segments(600.0, long_snd)
    covered = sum(b - a for a, b in segs)
    assert covered > 600.0 * 0.9           # split, not trimmed


# --------------------------------------------------------------------------
# Only the pause joins get a dissolve
# --------------------------------------------------------------------------


def test_dissolve_lands_on_pause_joins_only():
    e = entry(0.5, duration=25.0)
    e["sound"] = sound([[10.0, 14.0]])
    shots, _meta = scaffold.shots_for(e, 1)
    assert shots[0].dissolve == 0.0        # first piece cuts in, as always
    assert shots[1].dissolve > 0.0         # the join where a pause was cut


def test_broll_never_dissolves():
    shots, _ = scaffold.shots_for(entry(0.0, has=False, duration=30.0), 1)
    assert all(s.dissolve == 0.0 for s in shots)


# --------------------------------------------------------------------------
# Making it a particular length
# --------------------------------------------------------------------------


def stills(n, secs=4.5):
    shots = [Shot(src=f"media/{i}.jpg", kind="still", duration=secs,
                  id=f"s{i:02d}") for i in range(n)]
    meta = [{"entry": {"path": f"media/{i}.jpg"}, "role": None} for i in range(n)]
    return shots, meta


def total(shots):
    return sum(s.duration for s in shots if s.duration > 0)


def test_pictures_are_shortened_to_hit_the_target():
    shots, meta = stills(12)
    scaffold.fit_to_target(shots, meta, 30.0)
    assert abs(total(shots) - 30.0) < 0.5


def test_speech_is_never_shortened_to_hit_a_target():
    """The rule that outranks the target."""
    talk = Shot(src="media/x.mkv", kind="video", duration=76.0, id="s01")
    shots = [talk] + stills(3)[0]
    meta = [{"entry": {}, "talking": True, "part": 1, "parts": 1}] + stills(3)[1]
    scaffold.fit_to_target(shots, meta, 45.0)
    assert talk.duration == 76.0


def test_a_target_that_is_already_met_changes_nothing():
    shots, meta = stills(4)
    scaffold.fit_to_target(shots, meta, 300.0)
    assert total(shots) == 18.0


def test_faces_and_title_cards_survive_a_tight_target():
    shots, meta = stills(10)
    meta[0] = {"entry": {}, "role": "open"}
    meta[1] = {"entry": {"focus_from": "face"}, "role": None}
    meta[9] = {"entry": {}, "role": "close"}
    scaffold.fit_to_target(shots, meta, 12.0)
    for keep in (0, 1, 9):
        assert shots[keep].duration > 0, "a face or a title card was dropped"


# --------------------------------------------------------------------------
# Filename hints
# --------------------------------------------------------------------------


def test_filename_hints():
    assert scaffold._hint("00_beach") == (None, 0, "beach")
    assert scaffold._hint("open_hello")[0] == "open"
    assert scaffold._hint("close_bye")[0] == "close"
    assert scaffold._hint("open_close_logo")[0] == "open_close"
    assert scaffold._hint("quote_stay_curious")[0] == "quote"
    # A number and a role are independent, and both apply.
    role, num, _ = scaffold._hint("03_open_close_logo")
    assert (role, num) == ("open_close", 3)


def test_plain_filenames_get_no_role():
    assert scaffold._hint("PXL_20260827_113000") == (None, None,
                                                     "PXL_20260827_113000")


# --------------------------------------------------------------------------
# Timecodes
# --------------------------------------------------------------------------


def test_parse_time_accepts_every_shape_we_write():
    assert parse_time(12.5) == 12.5
    assert parse_time("12.5") == 12.5
    assert parse_time("2:14.5") == 134.5
    assert parse_time("00:02:14.5") == 134.5
    assert parse_time(None) == 0.0
