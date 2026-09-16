"""
speed: and the sound of a voice.

speed: was half-wired for a long time -- the picture honoured it, the
soundtrack and the captions did not. A shot at speed 1.2 poured 1.2
seconds of voice into a 1.0 second slot, so the voice ran long, drifted
out of sync, and every shot after it inherited the error. The captions
fired progressively later across the shot for the same reason.

Nothing here touches ffmpeg or a file. These are the numbers only.
"""

import re

from pytest import approx

from ffilm.audio import (CLICK_FADE, DEFAULT_TUNING, GATE_FRACTION,
                         LEVEL_MAX_LIFT_DB, LEVEL_TARGET_LUFS, SPEECH_NORM,
                         TRUST_RANGE_DB, VOICE_FLOOR_HZ, Tuning, atempo_chain,
                         duck_threshold, level_gain, place_chain, speech_chain,
                         tuning_for, voice_tone, voiced_chain)


def at(chain, name):
    """Where a filter sits in a chain, found by NAME. The two thresholds
    now carry this take's own numbers, so matching on the whole string
    would be matching on the material."""
    return next(i for i, f in enumerate(chain) if f.startswith(name))
from ffilm.caption_fit import fit_per_clip
from ffilm.spec import Film, Shot
from ffilm.voice import Line, VoiceSource


def factors(chain):
    return [float(m.group(1))
            for m in (re.fullmatch(r"atempo=([\d.]+)", c) for c in chain) if m]


def fade_out_at(chain):
    for c in chain:
        m = re.match(r"afade=t=out:st=([\d.]+):", c)
        if m:
            return float(m.group(1))
    return None


# --------------------------------------------------------------------------
# atempo: faster, not higher
# --------------------------------------------------------------------------

def test_a_modest_speed_up_is_one_filter():
    assert atempo_chain(1.2) == ["atempo=1.200000"]


def test_the_factors_always_multiply_back_to_the_speed_asked_for():
    for speed in (0.4, 0.5, 0.75, 1.0, 1.2, 1.5, 2.0, 3.0, 5.0):
        product = 1.0
        for f in factors(atempo_chain(speed)):
            product *= f
        assert abs(product - speed) < 1e-6, speed


def test_no_single_factor_leaves_the_range_old_ffmpeg_accepts():
    """Builds before 2022 reject atempo outside 0.5..2.0, with an error
    that names the filter and not the film.yaml line that caused it."""
    for speed in (0.2, 0.4, 3.0, 5.0, 9.0):
        for f in factors(atempo_chain(speed)):
            assert 0.5 <= f <= 2.0, (speed, f)


# --------------------------------------------------------------------------
# The chain one spoken take goes through
# --------------------------------------------------------------------------

def test_normal_speed_adds_no_tempo_filter_at_all():
    """Every film made before this existed must sound exactly as it did."""
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=True)
    assert not any("atempo" in c for c in chain)


def test_a_sped_up_take_gets_its_tempo_changed():
    chain = speech_chain(0.0, 12.0, 0, 1.2, lift=True)
    assert factors(chain) == [1.2]


def test_tempo_runs_before_the_normaliser():
    """Otherwise the normaliser's rise and fall are tuned to a timeline
    nobody ever hears."""
    chain = speech_chain(0.0, 12.0, 0, 1.2, lift=True)
    assert chain.index("atempo=1.200000") < chain.index(SPEECH_NORM)


def test_the_fade_out_lands_inside_the_sped_up_segment():
    """THE bug. 12 source seconds at 1.2x is a 10 second stream, so the
    fade belongs just before 10s. Scheduling it at 12s -- the old
    behaviour -- puts it past the end, where it does nothing at all."""
    chain = speech_chain(0.0, 12.0, 0, 1.2, lift=True)
    st = fade_out_at(chain)
    assert abs(st - (10.0 - CLICK_FADE)) < 1e-6
    assert st + CLICK_FADE <= 10.0 + 1e-9


def test_the_fade_out_is_unchanged_when_nothing_is_sped_up():
    chain = speech_chain(0.0, 12.0, 0, 1.0, lift=True)
    assert abs(fade_out_at(chain) - (12.0 - CLICK_FADE)) < 1e-6


def test_a_slowed_down_take_fades_at_its_longer_length():
    chain = speech_chain(0.0, 5.0, 0, 0.5, lift=True)
    assert abs(fade_out_at(chain) - (10.0 - CLICK_FADE)) < 1e-6


def test_a_sliver_of_audio_gets_no_fades():
    """Fading 20ms in and 20ms out of a 100ms segment is just a hole."""
    chain = speech_chain(3.0, 3.1, 0, 1.0, lift=True)
    assert fade_out_at(chain) is None


def test_a_segment_that_is_only_short_once_sped_up_gets_no_fades():
    """0.24s of source is long enough. At 2x it is 0.12s and is not."""
    assert fade_out_at(speech_chain(0.0, 0.24, 0, 1.0, lift=True)) is not None
    assert fade_out_at(speech_chain(0.0, 0.24, 0, 2.0, lift=True)) is None


def test_a_narration_track_is_never_trimmed_sped_or_faded():
    """It plays under the whole film. It has no shot, so it has no speed."""
    chain = speech_chain(0.0, None, 0, 1.0, lift=True)
    assert not any(c.startswith("atrim") for c in chain)
    assert not any("atempo" in c for c in chain)
    assert fade_out_at(chain) is None


def test_the_delay_is_last_so_it_moves_the_finished_stream():
    chain = speech_chain(0.0, 12.0, 4500, 1.2, lift=True)
    assert chain[-1] == "adelay=4500|4500"


# --------------------------------------------------------------------------
# The trim is measured on the SOURCE's clock, from the head of the file
#
# `-ss` before `-i` was tried here, to stop ffmpeg decoding a whole take
# from the top once per spoken piece. Measured on two real films it was
# worth 0.8% -- the cost is loudnorm and the voice chain, never the
# decode -- and it moved two of six pieces by 19 and 29ms, which is a
# quarter of a frame, on a face. The note in audio.py has the figures.
#
# These pin the shape that made the difference visible, so that anything
# which starts the decode late has to change a test that says why not.
# --------------------------------------------------------------------------


def trim_of(chain):
    for c in chain:
        if c.startswith("atrim"):
            return c
    return None


def test_the_trim_is_written_on_the_sources_own_clock():
    """Not on a clock rebased by a seek. A shot 90 seconds into a take
    trims at 90 seconds, and the number in film.yaml is that number."""
    chain = speech_chain(90.0, 97.0, 4500, 1.2, lift=True)
    assert trim_of(chain) == "atrim=start=90.000:end=97.000"


def test_the_window_kept_is_exactly_as_long_as_it_was_asked_for():
    """A trim that kept the wrong length would shorten the speech, and a
    shortened piece of speech is every later shot out of sync."""
    for start, end in ((0.0, 7.0), (90.0, 97.0), (133.67, 135.62)):
        m = re.fullmatch(r"atrim=start=([\d.]+):end=([\d.]+)",
                         trim_of(speech_chain(start, end, 0, 1.0, lift=True)))
        assert abs((float(m.group(2)) - float(m.group(1)))
                   - (end - start)) < 1e-3, (start, end)


def test_a_narration_track_at_offset_zero_is_never_trimmed():
    assert trim_of(speech_chain(0.0, None, 0, 1.0, lift=True)) is None


def test_a_narration_track_with_an_offset_trims_from_it():
    assert trim_of(speech_chain(30.0, None, 0, 1.0, lift=True)) \
        == "atrim=start=30.000"


# --------------------------------------------------------------------------
# The voice: EQ, never pitch
# --------------------------------------------------------------------------

def test_speech_lift_false_leaves_the_voice_completely_alone():
    """The one switch in film.yaml that means: my recording is fine."""
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=False)
    assert not any("highpass" in c or "equalizer" in c or "speechnorm" in c
                   or "afftdn" in c or "agate" in c for c in chain)


# --------------------------------------------------------------------------
# The waterfall between the sentences
# --------------------------------------------------------------------------

def test_the_expander_is_not_allowed_to_lift_the_room():
    """Expansion does not know what speech is -- it lifts whatever is
    quiet, and between two sentences the only quiet thing is the room.
    Measured on a real take, the same second of room tone: raw -45.3dB,
    through e=25 it came out at -17.5dB, against a voice at -15.0dB. The
    room was arriving within 2.5dB of the person talking, and it sounded
    like a waterfall."""
    e = float(re.search(r"e=([\d.]+)", SPEECH_NORM).group(1))
    assert e <= 12, "high expansion is what made the gaps roar"


def test_the_hiss_is_taken_out_before_it_is_amplified():
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=True)
    assert at(chain, "afftdn") < at(chain, "speechnorm")


def test_the_gate_closes_after_the_expansion_not_before():
    """A gate ahead of the normaliser is pointless -- whatever leaks
    through gets expanded anyway. Measured: placed first it changed the
    room tone by exactly 0.0dB; placed last, by -48.6dB."""
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=True)
    assert at(chain, "agate") > at(chain, "speechnorm")


def test_the_tone_shaping_arrives_with_the_lift():
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=True)
    assert f"highpass=f={VOICE_FLOOR_HZ}" in chain
    assert any(c.startswith("equalizer=") for c in chain)


def test_the_floor_is_removed_before_the_warmth_is_added():
    """Otherwise the shelf lifts rumble that is about to be discarded."""
    tone = voice_tone()
    assert "highpass" in tone[0]
    assert "equalizer" in tone[1]


def test_deeper_is_never_done_by_pitch_shifting():
    """asetrate lowers your voice and also makes it somebody else's.
    If this fails, someone reached for the wrong filter."""
    chain = speech_chain(0.0, 5.0, 0, 1.2, lift=True)
    assert not any("asetrate" in c or "rubberband" in c for c in chain)


# --------------------------------------------------------------------------
# Captions on a sped-up shot
# --------------------------------------------------------------------------

def clip_film(speed, duration=10.0, tout=12.0):
    shot = Shot(src="media/talk.mp4", kind="video", duration=duration,
                tin=0.0, tout=tout, speed=speed, id="s01")
    return Film(shots=[shot])


def source(film):
    return VoiceSource(audio_path=None, label="talk.mp4",
                       shot_srcs=[s.src for s in film.shots])


def test_a_line_on_a_normal_shot_lands_where_it_was_said():
    film = clip_film(1.0, duration=12.0, tout=12.0)
    caps, _ = fit_per_clip(film, source(film),
                           [Line(text="hello", start=6.0, end=8.0)])
    assert abs(caps["s01"][0].at - 6.0) < 0.01


def test_a_line_on_a_sped_up_shot_lands_earlier_by_exactly_the_speed():
    """Said 6s into the take. The take now plays 1.2x, so it is heard 5s
    in. The old code wrote 6.0 -- a second late, and later still for
    every line after it."""
    film = clip_film(1.2)
    caps, _ = fit_per_clip(film, source(film),
                           [Line(text="hello", start=6.0, end=8.0)])
    assert abs(caps["s01"][0].at - 5.0) < 0.01


def test_the_caption_is_held_for_less_time_too():
    """A 2 second line spoken at 1.2x is on screen for 1.67s. Holding it
    the full 2s walks it over the line that follows."""
    film = clip_film(1.2)
    caps, _ = fit_per_clip(film, source(film),
                           [Line(text="hello", start=6.0, end=8.0)])
    assert abs(caps["s01"][0].dur - 2.0 / 1.2) < 0.01


def test_no_caption_is_ever_scheduled_past_the_end_of_its_shot():
    """The failure this all exists to prevent: check rejects a caption
    that runs past its shot, so getting this wrong stops the render."""
    film = clip_film(1.2)
    lines = [Line(text=f"line {i}", start=float(i), end=float(i) + 1.5)
             for i in range(0, 12)]
    caps, _ = fit_per_clip(film, source(film), lines)
    for c in caps.get("s01", []):
        assert c.at + c.dur <= film.shots[0].duration + 1e-6, c.text


# --------------------------------------------------------------------------
# speed: has to survive the browser bench
# --------------------------------------------------------------------------

YAML = """fps: 24
resolution: [1080, 1920]
music_volume: 0.4

shots:

  - id: s01
    src: media/rec_20260828-101840.mp4
    in: "00:00.00"
    out: "00:04.03"
    speed: 1.2
    move: tilt_up
    focus: [0.500, 0.500]
"""


def test_the_bench_does_not_eat_the_speed_when_you_press_save(tmp_path):
    """The bench computes out: FROM the speed, so dropping speed: does
    not merely revert the shot -- it keeps the longer out-point and
    plays it at 1.0, so the shot silently grows 20% on every save."""
    from ffilm.editor import dump, state

    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "rec_20260828-101840.mp4").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text(YAML, encoding="utf-8")
    before = Film.load(tmp_path / "film.yaml")

    (tmp_path / "film.yaml").write_text(
        dump(tmp_path, state(tmp_path)), encoding="utf-8")
    after = Film.load(tmp_path / "film.yaml")

    assert after.shots[0].speed == before.shots[0].speed
    assert abs(after.shots[0].duration - before.shots[0].duration) < 0.02


def test_the_bench_still_carries_everything_else_across(tmp_path):
    from ffilm.editor import dump, state

    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "rec_20260828-101840.mp4").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text(YAML, encoding="utf-8")
    (tmp_path / "film.yaml").write_text(
        dump(tmp_path, state(tmp_path)), encoding="utf-8")
    assert Film.load(tmp_path / "film.yaml").music_volume == 0.4


# --------------------------------------------------------------------------
# Framing: a photograph is explored, a person is framed
# --------------------------------------------------------------------------

def test_a_still_only_leans_a_third_of_the_way_towards_its_subject():
    """Drifting from the middle towards the subject IS the move on a
    photograph. Honouring the focus point in full would leave nowhere
    to go."""
    from ffilm.moves import windows_for
    shot = Shot(src="a.jpg", kind="still", duration=5.0, move="static",
                focus=(0.9, 0.5), id="s01")
    f, _ = windows_for(shot)
    assert abs(f.cx - (0.5 + 0.4 * 0.35)) < 1e-6


def test_a_clip_is_framed_on_the_speaker_in_full():
    """A talking head has nowhere to drift to: either the person is
    centred or their ear is out of frame."""
    from ffilm.moves import windows_for
    shot = Shot(src="a.mp4", kind="video", duration=5.0, move="static",
                focus=(0.9, 0.5), id="s01")
    f, _ = windows_for(shot)
    assert abs(f.cx - 0.9) < 1e-6


def test_a_clip_is_not_zoomed_in_on_top_of_its_crop():
    """16:9 into 9:16 already keeps only 32% of the width. BASE on top of
    that is more of the speaker cut off and more sharpness thrown away."""
    from ffilm.moves import BASE, windows_for
    still = Shot(src="a.jpg", kind="still", duration=5, move="static", id="s")
    clip = Shot(src="a.mp4", kind="video", duration=5, move="static", id="s")
    assert windows_for(still)[0].scale == BASE
    assert windows_for(clip)[0].scale == 1.0


def test_a_hand_tuned_shot_is_still_never_second_guessed():
    from ffilm.moves import windows_for
    from ffilm.spec import Window
    shot = Shot(src="a.mp4", kind="video", duration=5.0, id="s01",
                frm=Window(0.2, 0.3, 1.4, 0.0), to=Window(0.8, 0.7, 1.1, 0.0))
    f, t = windows_for(shot)
    assert (f.cx, t.cx, f.scale) == (0.2, 0.8, 1.4)


# --------------------------------------------------------------------------
# One clock for the picture and the sound
# --------------------------------------------------------------------------

def test_a_shot_is_a_whole_number_of_frames():
    from ffilm.spec import frames_for
    assert frames_for(4.0, 24) == 96
    assert frames_for(5.03, 24) == 121          # 120.72 rounded
    assert frames_for(0.001, 24) == 1           # never nothing


def test_the_soundtrack_stands_where_the_picture_stands():
    """The bug this replaces: the picture advances a whole frame at a
    time and the soundtrack advanced by film.yaml's decimals, so they
    parted company a little at every cut and the gap was the running
    total of every rounding so far. Measured on a real ten-shot film:
    shot 1 dead in sync, shot 4 thirty-three milliseconds adrift, which
    on a face is visible."""
    from ffilm.spec import frames_for
    fps = 24
    # the real durations from Evening_2026-09-05, which is where it showed
    durations = [4.0, 6.175, 2.6, 14.258, 2.492, 4.65, 72.25, 1.133, 21.233]

    picture, f = [], 0
    for d in durations:
        picture.append(f / fps)
        f += frames_for(d, fps)

    sound, a = [], 0
    for d in durations:
        sound.append(round(a / fps * 1000) / 1000)      # adelay takes ms
        a += frames_for(d, fps)

    for p, s in zip(picture, sound):
        assert abs(p - s) < 0.002, "sound and picture must share a clock"

    # ...and the old way really did drift, or the assertion above proves
    # nothing at all.
    naive, t = [], 0.0
    for d in durations:
        naive.append(t)
        t += d
    assert max(abs(p - n) for p, n in zip(picture, naive)) > 0.02


# --------------------------------------------------------------------------
# Ducking that means decibels
# --------------------------------------------------------------------------


def test_asking_for_more_duck_gets_more_duck():
    """It used not to. music_duck set only the ratio against a threshold
    14dB under the voice, so the whole knob was worth 3dB and every
    setting ducked hard -- measured 8.1dB at 0.1 and 10.8dB at 0.5."""
    thresholds = [duck_threshold(d) for d in (0.1, 0.3, 0.5, 0.8, 1.0)]
    assert thresholds == sorted(thresholds, reverse=True), \
        "a deeper duck must mean a lower threshold"
    assert thresholds[0] / thresholds[-1] > 3.0, "the knob still does nothing"


def test_the_duck_is_clamped_to_its_own_range():
    assert duck_threshold(-1.0) == duck_threshold(0.0)
    assert duck_threshold(9.9) == duck_threshold(1.0)


def test_a_full_duck_puts_the_threshold_well_under_a_speaking_voice():
    from ffilm.audio import DUCK_MAX_DB, KEY_LEVEL_DB
    import math
    at_full = 20 * math.log10(duck_threshold(1.0))
    assert at_full < KEY_LEVEL_DB - DUCK_MAX_DB


# --------------------------------------------------------------------------
# Voicing the take once, and cutting the pieces out of the result
#
# The voice chain used to run per spoken piece, so every piece started
# speechnorm (an expander that has not heard the voice yet, and opens at
# full gain on room tone) and agate (which starts OPEN) cold. One take
# kept whole has one such burst, under the opening music fade. The same
# take cut at its 34 pauses had 35, one on every join -- measured, a
# room-tone step across the joins of median 11.5dB and worst 36.4dB.
#
# Now the take is voiced once and the pieces are cut from it. What these
# pin is the half that must not move: the piece is the same length, in
# the same place, as it always was.
# --------------------------------------------------------------------------


VOICE_FILTERS = ("afftdn", "speechnorm", "agate")


def test_the_voice_is_shaped_once_per_take_not_once_per_piece():
    once = voiced_chain(1.0, lift=True)
    piece = place_chain(40.0, 46.0, 4000, 1.0)
    for f in VOICE_FILTERS:
        assert any(c.startswith(f) for c in once), f
        assert not any(c.startswith(f) for c in piece), f
    assert not any("highpass" in c or "equalizer" in c for c in piece)


def test_nothing_in_a_piece_carries_state_across_a_cut():
    """That is the whole fix. A trim, a fade, a delay -- and the fade is
    the only one that touches a sample, for 20ms at each end."""
    piece = place_chain(40.0, 46.0, 4000, 1.2)
    allowed = ("atrim", "asetpts", "afade", "adelay")
    for c in piece:
        assert c.startswith(allowed), c


def test_the_speed_is_applied_once_with_the_voice():
    """Ahead of the normaliser, as speech_chain always did it, so the
    normaliser's rise and fall are measured on the heard timeline."""
    once = voiced_chain(1.4, lift=True)
    assert "atempo=1.400000" in once
    assert once.index("atempo=1.400000") < once.index(SPEECH_NORM)
    assert not any("atempo" in c for c in place_chain(40.0, 46.0, 0, 1.4))


def test_a_piece_is_cut_on_the_voiced_takes_own_clock():
    """The voiced take is already sped up, so a moment at t in the
    recording is at t/speed in it."""
    chain = place_chain(42.0, 49.0, 0, 1.4)
    m = re.fullmatch(r"atrim=start=([\d.]+):end=([\d.]+)", chain[0])
    assert abs(float(m.group(1)) - 42.0 / 1.4) < 1e-3
    assert abs(float(m.group(2)) - 49.0 / 1.4) < 1e-3


def test_the_piece_is_the_same_length_it_was_before():
    """A piece that changed length would move every shot after it."""
    for start, end, speed in ((2.45, 8.80, 1.4), (0.0, 5.0, 1.0),
                              (133.67, 135.62, 1.2)):
        was = fade_out_at(speech_chain(start, end, 0, speed, lift=True))
        now = fade_out_at(place_chain(start, end, 0, speed))
        if was is None:
            assert now is None, (start, end, speed)
        else:
            assert abs(was - now) < 1e-3, (start, end, speed)


def test_the_piece_lands_where_it_always_landed():
    for delay in (0, 4000, 96500):
        chain = place_chain(40.0, 46.0, delay, 1.2)
        if delay:
            assert chain[-1] == f"adelay={delay}|{delay}"
        else:
            assert not any("adelay" in c for c in chain)


def test_speech_lift_false_still_means_exactly_as_recorded():
    once = voiced_chain(1.0, lift=False)
    assert not any(f in once for f in VOICE_FILTERS)
    assert not any("highpass" in c or "equalizer" in c for c in once)


def test_a_narration_track_is_not_trimmed_at_the_end():
    chain = place_chain(0.0, None, 0, 1.0)
    assert not any(c.startswith("atrim") for c in chain)
    assert fade_out_at(chain) is None


def test_a_sliver_still_gets_no_fades():
    assert fade_out_at(place_chain(3.0, 3.1, 0, 1.0)) is None


# --------------------------------------------------------------------------
# Bringing a take to a known level
#
# Every absolute number downstream of this -- afftdn's nf, the gate's
# threshold, KEY_LEVEL_DB -- is only correct because this ran first.
# --------------------------------------------------------------------------

def test_a_quiet_take_is_lifted_to_the_target():
    assert level_gain(-42.0) == approx(22.0)


def test_a_loud_take_is_turned_down():
    assert level_gain(-8.0) == approx(-12.0)


def test_a_take_already_at_the_target_is_left_alone():
    assert level_gain(LEVEL_TARGET_LUFS) == approx(0.0)


def test_a_clip_with_no_voice_in_it_is_not_amplified():
    """An ambient clip measures near silence. Bringing that to -20 LUFS
    would turn a room into a roar, so it is left exactly as it is."""
    assert level_gain(-70.0) == 0.0
    assert level_gain(None) == 0.0


def test_the_lift_has_a_ceiling():
    """A take recorded catastrophically low should arrive quiet and
    obviously wrong, not as forty decibels of hiss."""
    assert level_gain(-59.0) == LEVEL_MAX_LIFT_DB


def test_the_level_is_set_before_anything_absolute_reads_it():
    """The ordering IS the fix. afftdn's nf and the gate's threshold are
    both dBFS, so a take that has not been levelled yet reads wrong to
    both of them."""
    chain = voiced_chain(1.0, lift=True,
                         tuning=Tuning(14.2, -45.0, -30.5))
    vol = next(i for i, f in enumerate(chain) if f.startswith("volume="))
    assert vol < next(i for i, f in enumerate(chain) if "afftdn" in f)
    assert vol < next(i for i, f in enumerate(chain) if "agate" in f)
    assert vol < next(i for i, f in enumerate(chain) if "speechnorm" in f)


def test_speech_lift_false_still_means_untouched():
    """Moving the level of a take is moving the take."""
    chain = voiced_chain(1.0, lift=False,
                         tuning=Tuning(14.2, -45.0, -30.5))
    assert not any(f.startswith("volume=") for f in chain)


# --------------------------------------------------------------------------
# The three numbers that follow the material
#
# `ingest` already decodes every take to find its pauses, and on the way
# it learns where that take's room sits and where its voice sits. These
# turn those two numbers into the gain, the denoiser's floor and the
# gate's line -- so a quiet flat and a noisy kitchen get different
# thresholds without anybody typing one.
# --------------------------------------------------------------------------

def test_a_noisy_room_gates_harder_than_a_quiet_one():
    """The whole point. Same voice level, different rooms."""
    quiet = tuning_for(room_db=-53.0, voice_db=-22.0)
    noisy = tuning_for(room_db=-38.0, voice_db=-22.0)
    assert noisy.gate_db > quiet.gate_db
    assert noisy.nf_db > quiet.nf_db


def test_the_gate_sits_between_the_room_and_the_voice():
    """Above the room so it closes on it, well under the voice so it
    never closes on a softly spoken word."""
    t = tuning_for(room_db=-53.0, voice_db=-22.0)
    room_at_gate = t.gate_db - (-22.0 - -53.0) * GATE_FRACTION
    assert room_at_gate < t.gate_db < room_at_gate + (-22.0 - -53.0)


def test_the_gate_agrees_with_where_ingest_cut():
    """ingest puts the line between room and voice at QUIET_FRACTION of
    the way up. A gate that closed somewhere else than where the edit cut
    would be the bug, so it uses the same fraction."""
    from ffilm.ingest import QUIET_FRACTION
    assert GATE_FRACTION == QUIET_FRACTION


def test_a_take_with_nothing_to_tell_apart_keeps_the_settled_numbers():
    """Constant traffic, or a take so hot the room and the voice are the
    same size. Set its level, but do not derive a threshold from a
    measurement that has just said it cannot see a difference."""
    t = tuning_for(room_db=-30.0, voice_db=-30.0 + TRUST_RANGE_DB - 1)
    assert t.nf_db == DEFAULT_TUNING.nf_db
    assert t.gate_db == DEFAULT_TUNING.gate_db
    assert t.gain_db != 0.0


def test_no_measurement_means_the_numbers_this_file_always_used():
    """A narration track kept outside media/, or a project whose
    analysis/ has been deleted. Not an error -- an ordinary state."""
    assert tuning_for(None, None) == DEFAULT_TUNING


def test_the_default_gate_is_the_one_that_was_there_before():
    """0.03 linear. Changing the fallback silently would change every
    film that has no analysis."""
    assert DEFAULT_TUNING.gate_threshold == approx(0.03, abs=0.0005)


def test_the_thresholds_stay_inside_what_ffmpeg_accepts():
    """afftdn refuses an nf outside -80..-20, and refusing is the good
    case -- it fails the render rather than the sound."""
    for room, voice in [(-90.0, -80.0), (-10.0, -2.0), (-70.0, -5.0)]:
        t = tuning_for(room, voice)
        assert -80.0 <= t.nf_db <= -20.0
        assert 0.0 < t.gate_threshold < 1.0


# --------------------------------------------------------------------------
# The gate before the expander
#
# For a long time the note in audio.py said a gate placed first measured
# EXACTLY no change. It did -- while the threshold was a constant sitting
# in the middle of the room's own scatter. Once the take is brought to a
# known level first, the same filter is worth 35dB at the worst point of
# a real recording.
# --------------------------------------------------------------------------

def test_there_is_a_gate_on_each_side_of_the_expander():
    t = tuning_for(room_db=-53.1, voice_db=-22.2)
    chain = voiced_chain(1.0, lift=True, tuning=t)
    gates = [i for i, f in enumerate(chain) if f.startswith("agate")]
    norm = at(chain, "speechnorm")
    assert len(gates) == 2, chain
    assert gates[0] < norm < gates[1]


def test_the_gate_before_sits_under_the_one_after():
    """They are the same line drawn on two different scales. Before the
    expander the room has not been lifted yet, so the line is lower."""
    t = tuning_for(room_db=-53.1, voice_db=-22.2)
    assert t.pre_gate_db < t.gate_db


def test_the_early_gate_is_placed_off_the_measured_room():
    """Not a constant. A noisier room has to move it up, or it is the
    bug it exists to fix."""
    quiet = tuning_for(room_db=-56.0, voice_db=-22.0)
    noisy = tuning_for(room_db=-38.0, voice_db=-22.0)
    assert noisy.pre_gate_db > quiet.pre_gate_db + 5


def test_no_measurement_means_no_gate_before():
    """A take ingest has never seen. Without knowing where the room is
    there is nowhere to put this gate, and a guess would be a gate across
    somebody's voice."""
    assert DEFAULT_TUNING.pre_gate_db is None
    assert DEFAULT_TUNING.pre_gate_threshold is None
    chain = voiced_chain(1.0, lift=True, tuning=DEFAULT_TUNING)
    assert len([f for f in chain if f.startswith("agate")]) == 1


def test_speech_lift_false_still_has_no_gates_at_all():
    t = tuning_for(room_db=-53.1, voice_db=-22.2)
    chain = voiced_chain(1.0, lift=False, tuning=t)
    assert not any(f.startswith("agate") for f in chain)


# --------------------------------------------------------------------------
# One voice chain, and a cache that knows when it changed
# --------------------------------------------------------------------------

from ffilm.audio import lift_filters, voiced_name

TUNED = Tuning(gain_db=9.3, nf_db=-46.9, gate_db=-39.3, pre_gate_db=-40.7)


def test_the_fallback_chain_shapes_the_voice_exactly_like_the_voiced_take():
    """The same filters were written out twice, once per path. A change to
    one and not the other would only show on the path that runs when
    voicing a take failed -- the one nobody listens to."""
    lift = lift_filters(TUNED)
    voiced = voiced_chain(1.0, True, TUNED)
    fallback = speech_chain(1.0, 5.0, 0, 1.0, True, TUNED)
    assert voiced[-len(lift):] == lift
    start = fallback.index(lift[0])
    assert fallback[start:start + len(lift)] == lift


def test_a_different_tuning_is_a_different_voiced_take():
    """The voiced take is cached on disk. Re-ingesting a take, or changing
    a constant, used to reuse the old file -- and the change was inaudible
    for no reason anybody could see."""
    base = voiced_name("rec_1", 1.2, True, voiced_chain(1.2, True, TUNED))
    retuned = Tuning(gain_db=9.3, nf_db=-46.9, gate_db=-35.0, pre_gate_db=-40.7)
    assert voiced_name("rec_1", 1.2, True, voiced_chain(1.2, True, retuned)) != base
    assert voiced_name("rec_1", 1.2, True, voiced_chain(1.2, True, TUNED)) == base


def test_a_voiced_take_is_still_named_for_its_take_and_speed():
    """The old-version sweep finds stale copies by that prefix."""
    name = voiced_name("rec_1", 1.2, True, voiced_chain(1.2, True, TUNED))
    assert name.startswith("rec_1__1200__lift__v")
    assert name.endswith(".wav")


def test_the_voice_character_comes_after_both_gates():
    """Measured with the tone shaping LAST, after the gates have closed
    the pauses. Moved in front of them, the gates would be judging a
    different signal than the one the numbers were taken on."""
    from ffilm.audio import VOICE_CHARACTER
    chain = lift_filters(TUNED, speech_model=False)
    last_gate = max(i for i, f in enumerate(chain) if f.startswith("agate"))
    assert chain[last_gate + 1:] == VOICE_CHARACTER
    assert lift_filters(TUNED)[-len(VOICE_CHARACTER):] == VOICE_CHARACTER


def test_the_speech_denoiser_comes_after_speechnorm_or_ffmpeg_hangs():
    """Measured 2026-09-16, ffmpeg 9.0.1: arnndn anywhere BEFORE speechnorm
    wrote 96% of the file and then hung at the end of the stream, every
    time -- three runs, three fixed frame sizes, 48k throughout, all hung.
    After it: 1.2s. A render that stops with no message is the worst
    thing this tool could do, so this order is a rule."""
    from ffilm.audio import SPEECH_DENOISE
    chain = lift_filters(TUNED)
    rnn = next(i for i, f in enumerate(chain) if f.startswith("arnndn"))
    norm = next(i for i, f in enumerate(chain) if f.startswith("speechnorm"))
    last_gate = max(i for i, f in enumerate(chain) if f.startswith("agate"))
    assert rnn > norm
    assert rnn > last_gate                  # where it was measured
    assert chain[rnn - 1:rnn + 2] == SPEECH_DENOISE


def test_the_speech_denoiser_runs_at_48k_and_comes_back():
    """RNNoise is a 48 kHz model; everything around it is 44.1."""
    from ffilm.audio import SPEECH_DENOISE
    assert SPEECH_DENOISE[0] == "aresample=48000"
    assert SPEECH_DENOISE[-1] == "aresample=44100"


def test_without_the_model_the_voice_is_still_shaped():
    """No network on a new computer: the film is still made, only the
    room under the words stays."""
    chain = voiced_chain(1.0, True, TUNED, speech_model=False)
    assert not any(f.startswith("arnndn") for f in chain)
    assert any(f.startswith("speechnorm") for f in chain)


def test_speech_lift_off_still_means_exactly_as_recorded():
    from ffilm.audio import VOICE_CHARACTER
    raw = voiced_chain(1.0, False, TUNED)
    assert not any(f in raw for f in VOICE_CHARACTER)


def test_the_end_of_a_voiced_take_is_silent():
    """RNNoise flushes a burst when the stream ends: the last 20 ms of the
    voiced take of "I am not your fear" peaked at +3 dBFS, and the final
    of 2026-09-16 ended on that click. Nothing said in the last 50 ms of
    a recording is worth that."""
    import numpy as np
    from ffilm.audio import TAKE_TAIL_SILENCE, silence_tail
    rate = 44100
    samples = np.full((rate, 2), 20000, dtype=np.int16)
    out = silence_tail(samples, rate)
    tail = int(TAKE_TAIL_SILENCE * rate)
    assert not out[-tail:].any()
    assert (out[: rate // 2] == 20000).all()          # the rest untouched
    assert np.abs(out[-tail - 1:-tail + 1]).max() < 20000   # faded, not cut


def test_a_take_shorter_than_the_tail_is_simply_silent():
    import numpy as np
    from ffilm.audio import silence_tail
    out = silence_tail(np.full((100, 2), 5, dtype=np.int16), 44100)
    assert not out.any()


def test_the_fallback_path_never_runs_the_denoiser_per_piece():
    """Per piece, RNNoise would flush its burst at the end of every piece,
    which is a click on every join."""
    import inspect
    from ffilm import audio
    src = inspect.getsource(audio.build_soundtrack)
    assert "speech_model = False" in src
