"""
A camera take keeps its last word.

Found 2026-09-24 on Frankfurt School vs Kołakowski: "domination" (intro)
and "disagreement" (closing) were cut mid-vowel. Since c802fcd the render
reads a camera take's sound `lag` seconds later than its picture (the
microphone starts late), but `film init` still placed the cuts on the
sound's own clock -- so every take lost its last `lag` seconds of speech.
Measured: lag 0.610 s and 0.617 s; 0.31 s and 0.36 s of the word lost.

The cuts are now placed on the picture's clock: sound time + lag.
"""

from ffilm import scaffold


def take(speech_in, speech_out, dur, quiet=()):
    return {"kind": "video", "path": "media/rec_20260924-100838.mp4",
            "duration": dur,
            "sound": {"has": True, "ratio": 0.5, "in": speech_in,
                      "out": speech_out, "quiet": [list(q) for q in quiet]}}


def test_the_last_cut_is_after_the_last_word_is_heard():
    # the Frankfurt intro: last word ends 27.66 s on the sound clock
    lag = 0.61
    segs = scaffold.video_segments(take(1.95, 27.66, 31.12), lag=lag)
    heard_until = segs[-1][1] - lag           # what speech_specs plays
    assert heard_until >= 27.66


def test_the_first_cut_is_before_the_first_word_is_heard():
    lag = 0.61
    segs = scaffold.video_segments(take(1.95, 27.66, 31.12), lag=lag)
    assert segs[0][0] - lag <= 1.95


def test_a_cut_never_runs_past_the_end_of_the_picture():
    segs = scaffold.video_segments(take(1.0, 29.9, 30.13), lag=0.62)
    assert segs[-1][1] <= 30.13


def test_the_pauses_move_with_the_words():
    # a 4 s pause at 10-14 on the sound clock is 10.5-14.5 on the picture's
    plain = scaffold.video_segments(take(1.0, 24.0, 30.0, [(10.0, 14.0)]))
    late = scaffold.video_segments(take(1.0, 24.0, 30.0, [(10.0, 14.0)]),
                                   lag=0.5)
    assert len(plain) == len(late) == 2
    for (a, b), (c, d) in zip(plain, late):
        assert abs(c - (a + 0.5)) < 0.011 and abs(d - (b + 0.5)) < 0.011


def test_without_a_lag_nothing_changes():
    e = take(1.0, 24.0, 30.0, [(10.0, 14.0)])
    assert scaffold.video_segments(e) == scaffold.video_segments(e, lag=0.0)
