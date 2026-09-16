"""
The music under a film longer than the track.

It used to be looped with `-stream_loop`: the track's own fade-out, a
second of digital silence, and its own slow intro, joined end to end. On
"I am not your fear" (2026-09-16) that put 17.5 seconds with no music at
all at 3:08, and a patch measuring -88 dBFS -- dead air -- in the final.

And every track came in at whatever level it was mastered at, under the
same `music_volume`. The two tracks on the machine that day measured
-13.5 and -44.3 LUFS: one film's music was louder than the voice between
sentences, another's could not be heard.

Numbers only here. Nothing touches ffmpeg.
"""

from pytest import approx

from ffilm.audio import (MUSIC_CROSSFADE, MUSIC_MAX_REPEATS, MUSIC_TARGET_LUFS,
                         music_gain, music_plan, parse_music_measure)


STELLARDRONE = """
[Parsed_silencedetect_1 @ 0000] silence_start: 0
[Parsed_silencedetect_1 @ 0000] silence_end: 3.535442 | silence_duration: 3.535442
[Parsed_silencedetect_1 @ 0000] silence_start: 192.138526
[Parsed_ebur128_0 @ 0000] Summary:
  Integrated loudness:
    I:         -13.5 LUFS
[Parsed_silencedetect_1 @ 0000] silence_end: 195.692313 | silence_duration: 3.553787
"""


def test_the_measurement_finds_the_loudness_and_the_silent_ends():
    m = parse_music_measure(STELLARDRONE, duration=195.692313)
    assert m.lufs == approx(-13.5)
    assert m.head == approx(3.535, abs=0.01)
    assert m.tail == approx(192.139, abs=0.01)


def test_a_quiet_passage_in_the_middle_is_not_mistaken_for_the_end():
    text = """
[x] silence_start: 80.0
[x] silence_end: 82.0 | silence_duration: 2.0
    I:         -18.0 LUFS
"""
    m = parse_music_measure(text, duration=200.0)
    assert m.head == 0.0
    assert m.tail == 200.0


def test_a_track_with_no_silence_is_used_whole():
    m = parse_music_measure("    I:         -20.0 LUFS\n", duration=100.0)
    assert (m.head, m.tail) == (0.0, 100.0)


def test_an_unreadable_measurement_changes_nothing():
    m = parse_music_measure("garbage", duration=0.0)
    assert m.lufs is None


def test_a_track_longer_than_the_film_is_played_once():
    assert music_plan(0.0, 600.0, total=200.0).repeats == 1


def test_a_track_shorter_than_the_film_is_repeated_with_a_crossfade():
    """What that film needed: 188.6s of usable track under 178.7s is once;
    under 215.9s it is twice, joined by a crossfade, not by silence."""
    once = music_plan(3.535, 192.139, total=178.7)
    twice = music_plan(3.535, 192.139, total=215.9)
    assert once.repeats == 1
    assert twice.repeats == 2
    assert twice.crossfade == approx(MUSIC_CROSSFADE)


def test_the_repeats_always_cover_the_film():
    for usable, total in ((10.0, 95.0), (30.0, 31.0), (60.0, 600.0)):
        p = music_plan(0.0, usable, total)
        if p.repeats < MUSIC_MAX_REPEATS:
            assert p.repeats * usable - (p.repeats - 1) * p.crossfade >= total


def test_a_jingle_under_a_long_film_stops_repeating_and_says_so():
    p = music_plan(0.0, 5.0, total=600.0)
    assert p.repeats == MUSIC_MAX_REPEATS
    assert p.short_by > 0


def test_a_very_short_track_gets_a_crossfade_it_can_hold():
    p = music_plan(0.0, 4.0, total=20.0)
    assert p.crossfade < 4.0 / 2


def test_a_quiet_track_and_a_loud_track_land_on_the_same_bed_level():
    assert -13.5 + music_gain(-13.5) == approx(MUSIC_TARGET_LUFS)
    assert -44.3 + music_gain(-44.3) == approx(MUSIC_TARGET_LUFS)


def test_music_nothing_can_measure_is_left_alone():
    assert music_gain(None) == 0.0
    assert music_gain(-75.0) == 0.0


def test_the_gain_on_music_is_bounded():
    assert music_gain(-59.0) <= 30.0
    assert music_gain(+5.0) >= -20.0


def test_the_ends_of_a_track_are_judged_against_its_own_loudness():
    """A fixed -50dB line trimmed 3.5s off a track whose fade-out takes
    25s, and the repeat still left 11s of near-silence at the join. A
    loud track's fade is long; a quiet track is quiet all the way."""
    from ffilm.audio import MUSIC_SILENCE_DB, music_silence_threshold
    assert music_silence_threshold(-13.5) == approx(-31.5)
    assert music_silence_threshold(-44.3) == approx(-62.3)
    assert music_silence_threshold(None) == MUSIC_SILENCE_DB


def test_the_check_says_when_the_music_will_repeat():
    from ffilm.audio import MusicMeasure
    from ffilm.checks import music_note
    red_giant = MusicMeasure(-13.5, 10.9, 187.0, 195.7)
    assert music_note(red_giant, 178.7) is None
    said = music_note(red_giant, 215.9)
    assert "176s of music" in said and "215.9s film" in said
    assert "repeats once" in said


def test_the_check_says_when_the_music_will_stop_early():
    from ffilm.audio import MusicMeasure
    from ffilm.checks import music_note
    said = music_note(MusicMeasure(-20.0, 0.0, 5.0), 600.0)
    assert "stops" in said


def test_a_film_just_past_the_trimmed_track_plays_into_its_own_fade():
    """176s of loud track, a 178.7s film, and 8.7s of the track's own
    fade-out still there. Restarting the song 2.6s before the end, under
    the film's fade, would be worse than letting it finish."""
    p = music_plan(10.9, 187.0, total=178.7, length=195.7)
    assert p.repeats == 1
    assert p.end == approx(10.9 + 178.7)


def test_a_film_past_the_whole_track_still_repeats():
    p = music_plan(10.9, 187.0, total=215.9, length=195.7)
    assert p.repeats == 2
    assert p.end == approx(187.0)
