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

from ffilm.audio import (CLICK_FADE, DENOISE, NOISE_GATE, SPEECH_NORM,
                         VOICE_FLOOR_HZ, atempo_chain, duck_threshold,
                         speech_chain, voice_tone)
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
    assert chain.index(DENOISE) < chain.index(SPEECH_NORM)


def test_the_gate_closes_after_the_expansion_not_before():
    """A gate ahead of the normaliser is pointless -- whatever leaks
    through gets expanded anyway. Measured: placed first it changed the
    room tone by exactly 0.0dB; placed last, by -48.6dB."""
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=True)
    assert chain.index(NOISE_GATE) > chain.index(SPEECH_NORM)


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
