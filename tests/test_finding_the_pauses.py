"""
Where the pauses are, and why ffmpeg could not tell us.

Every one of these is the bug that reached a finished film: a 310 second
take came back with NO pauses at all and was left whole, 310 seconds of
one shot with the room tone still in it -- which then chattered the noise
gate and put crackling in every gap.

`silence_floor` measured the take's mean RMS and handed the number to
ffmpeg's `silencedetect`, which compares PEAK samples. Measured on that
take: pauses at -46 dBFS RMS, peaking -33 dBFS; threshold given, -39.
Two different quantities about 10dB apart, so not one moment of that take
ever counted as quiet.

Nothing here touches ffmpeg or a recording. These are the numbers only.
"""

import numpy as np

from ffilm.ingest import (LEVEL_RATE, LEVEL_WINDOW, NEEDS_RANGE_DB,
                          quiet_stretches, window_levels)


def db_to_rms(db):
    return 32768.0 * 10 ** (db / 20.0)


def noise(seconds, db, rng):
    """Room tone at a given RMS level. Gaussian, so its peaks sit about
    12dB above its RMS -- which is the whole point of these tests."""
    n = int(LEVEL_RATE * seconds)
    return rng.normal(0.0, db_to_rms(db), n)


def speech(seconds, db, rng):
    return rng.normal(0.0, db_to_rms(db), int(LEVEL_RATE * seconds))


def take(parts, seed=0):
    """A take built out of (kind, seconds) pieces, and where its pauses
    really are. `room` is a pause; `talk` is not."""
    rng = np.random.default_rng(seed)
    pieces, truth, t = [], [], 0.0
    for kind, secs in parts:
        if kind == "room":
            pieces.append(noise(secs, -46.0, rng))
            truth.append((t, t + secs))
        else:
            pieces.append(speech(secs, -20.0, rng))
        t += secs
    return np.concatenate(pieces).astype(np.int16), truth


def covered(found, want, slack=0.25):
    """Did we find a pause sitting on top of each real one?"""
    for a, b in want:
        if not any(f <= a + slack and g >= b - slack for f, g in found):
            return False
    return True


# --------------------------------------------------------------------------
# Measuring the level
# --------------------------------------------------------------------------


def test_silence_measures_as_silence():
    lv = window_levels(np.zeros(LEVEL_RATE, dtype=np.int16))
    assert lv.size == int(1.0 / LEVEL_WINDOW)
    assert lv.max() < -100.0


def test_full_scale_measures_as_zero():
    full = np.full(LEVEL_RATE, 32767, dtype=np.int16)
    assert abs(window_levels(full).mean()) < 0.1


def test_a_known_level_measures_as_that_level():
    rng = np.random.default_rng(1)
    for want in (-20.0, -35.0, -46.0):
        pcm = rng.normal(0.0, db_to_rms(want), LEVEL_RATE * 2).astype(np.int16)
        assert abs(window_levels(pcm).mean() - want) < 1.5, want


def test_a_take_shorter_than_one_window_is_not_a_crash():
    assert window_levels(np.zeros(10, dtype=np.int16)).size == 0
    assert quiet_stretches(np.zeros(0), 1.5) == ([], -32.0)


# --------------------------------------------------------------------------
# Finding the pauses
# --------------------------------------------------------------------------


def test_the_pauses_that_were_put_in_are_the_pauses_that_come_out():
    pcm, want = take([("talk", 4), ("room", 3), ("talk", 4),
                      ("room", 2), ("talk", 3)])
    found, _line = quiet_stretches(window_levels(pcm), 1.5)
    assert len(found) == 2
    assert covered(found, want)


def test_room_tone_whose_PEAKS_break_the_line_is_still_a_pause():
    """THE bug. Gaussian room tone at -46 dBFS RMS peaks around -34, so
    every peak-based test of it fails while the pause is plainly there.
    This asserts both halves: we find the pause, AND the peaks really do
    break the line we judged it by -- so this is the case that used to be
    missed, not a case that was always easy."""
    pcm, want = take([("talk", 4), ("room", 4), ("talk", 4)])
    levels = window_levels(pcm)
    found, line = quiet_stretches(levels, 1.5)

    assert covered(found, want), "the pause was missed"

    room = pcm[int(LEVEL_RATE * 4.2):int(LEVEL_RATE * 7.8)]
    peak_db = 20 * np.log10(np.abs(room).max() / 32768.0)
    assert peak_db > line, (
        "this take is not the hard case -- its peaks stay under the line, "
        "so it would not have caught the original bug")


def test_a_pause_running_to_the_very_end_is_found():
    pcm, want = take([("talk", 4), ("room", 3)])
    found, _ = quiet_stretches(window_levels(pcm), 1.5)
    assert covered(found, want)


def test_a_pause_at_the_very_start_is_found():
    pcm, want = take([("room", 3), ("talk", 4)])
    found, _ = quiet_stretches(window_levels(pcm), 1.5)
    assert covered(found, want)


def test_a_short_gap_is_not_a_pause():
    """Speech without its breaths sounds panicked -- the same rule
    scaffold.PAUSE_DROP applies further down."""
    pcm, _ = take([("talk", 4), ("room", 0.4), ("talk", 4)])
    found, _ = quiet_stretches(window_levels(pcm), 1.5)
    assert found == []


def test_the_gap_has_to_beat_the_minimum_it_was_given():
    pcm, _ = take([("talk", 3), ("room", 2.0), ("talk", 3)])
    assert len(quiet_stretches(window_levels(pcm), 1.5)[0]) == 1
    assert quiet_stretches(window_levels(pcm), 3.0)[0] == []


# --------------------------------------------------------------------------
# When it cannot tell, it keeps everything
# --------------------------------------------------------------------------


def test_a_take_with_nothing_to_tell_apart_is_kept_whole():
    """Constant traffic, or a take recorded so hot that the room and the
    voice are the same size. Shredding it would be worse than leaving it,
    which is the rule scaffold.MAX_TRIM already follows."""
    rng = np.random.default_rng(3)
    flat = rng.normal(0.0, db_to_rms(-30.0), LEVEL_RATE * 12).astype(np.int16)
    found, _ = quiet_stretches(window_levels(flat), 1.5)
    assert found == []


def test_the_range_it_needs_is_the_one_it_says_it_needs():
    """Just under the limit keeps the take whole; comfortably over it
    finds the pause. Pins NEEDS_RANGE_DB to actual behaviour."""
    rng = np.random.default_rng(4)

    def built(gap_db):
        parts = [rng.normal(0.0, db_to_rms(-40.0 + gap_db), LEVEL_RATE * 4),
                 rng.normal(0.0, db_to_rms(-40.0), LEVEL_RATE * 4),
                 rng.normal(0.0, db_to_rms(-40.0 + gap_db), LEVEL_RATE * 4)]
        return np.concatenate(parts).astype(np.int16)

    assert quiet_stretches(window_levels(built(NEEDS_RANGE_DB - 4)), 1.5)[0] == []
    assert quiet_stretches(window_levels(built(NEEDS_RANGE_DB + 14)), 1.5)[0] != []


def test_pure_silence_between_speech_is_still_found():
    """The easy case must not have been broken by fixing the hard one."""
    rng = np.random.default_rng(5)
    parts = [rng.normal(0.0, db_to_rms(-20.0), LEVEL_RATE * 4),
             np.zeros(LEVEL_RATE * 3),
             rng.normal(0.0, db_to_rms(-20.0), LEVEL_RATE * 4)]
    pcm = np.concatenate(parts).astype(np.int16)
    found, _ = quiet_stretches(window_levels(pcm), 1.5)
    assert covered(found, [(4.0, 7.0)])
