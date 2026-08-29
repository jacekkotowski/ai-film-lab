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

from ffilm.audio import (CLICK_FADE, SPEECH_NORM, VOICE_FLOOR_HZ,
                         atempo_chain, speech_chain, voice_tone)
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
# The voice: EQ, never pitch
# --------------------------------------------------------------------------

def test_speech_lift_false_leaves_the_voice_completely_alone():
    """The one switch in film.yaml that means: my recording is fine."""
    chain = speech_chain(0.0, 5.0, 0, 1.0, lift=False)
    assert not any("highpass" in c or "equalizer" in c or "speechnorm" in c
                   for c in chain)


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
