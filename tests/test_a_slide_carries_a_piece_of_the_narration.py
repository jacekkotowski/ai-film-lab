"""
A slide is a shot with a piece of the narration on it.

Jacek's own test, `projects/test_story` -- three vertical pictures and a
59.5s voiceover, no script -- came back with the narration laid flat
under the whole film and the pictures stretched evenly to cover it:
23.3 / 19.1 / 19.1 seconds, which is not where any of the sentences
are. There was no way, in film.yaml, to say which picture goes with
which words.

A talking take already works the way it should: it is cut at its pauses,
each piece is a shot with `in:`/`out:` on the clip, and moving, trimming
or deleting that shot moves, trims or deletes the words with it. This
gives a photograph exactly the same handle, with the picture and the
sound coming from two files instead of one:

    - id: s01
      src: media/1declaration_of_love.png
      voice: media/voiceover_20260917-105656.wav
      in: "00:02.05"
      out: "00:18.20"

Everything downstream of that is already built: `audio.build_soundtrack`
voices each take once and cuts pieces out of it, `caption_fit` fits
lines per source. This is what makes a still look like one more piece.

Numbers and strings only. No ffmpeg, no rendering, no speech model.
"""

from pathlib import Path

import pytest
from pytest import approx

from ffilm import caption_fit, checks, voice as voice_mod
from ffilm.audio import speech_specs
from ffilm.spec import VOICE_TAIL, Film, Shot
from ffilm.voice import Line


def slide(sid, src, voice, tin, tout, **kw) -> Shot:
    return Shot.parse({"id": sid, "src": src, "voice": voice,
                       "in": tin, "out": tout, **kw}, 0)


# --------------------------------------------------------------------------
# What film.yaml now means
# --------------------------------------------------------------------------

def test_a_still_with_a_voice_holds_for_its_words_and_a_breath_after():
    s = slide("s01", "media/a.png", "media/vo.wav", 2.05, 18.20)
    assert s.kind == "still"
    assert s.voice == "media/vo.wav"
    assert s.tin == approx(2.05)
    assert s.tout == approx(18.20)
    assert s.duration == approx(18.20 - 2.05 + VOICE_TAIL)


def test_the_picture_can_be_held_longer_than_the_words():
    """`duration` still wins where it is written. The words do not
    stretch with it -- they are where they were said."""
    s = slide("s02", "media/a.png", "media/vo.wav", 2.0, 8.0, duration=20.0)
    assert s.duration == approx(20.0)
    assert (s.tin, s.tout) == (approx(2.0), approx(8.0))


def test_a_timecode_is_read_the_same_way_it_is_on_a_clip():
    s = slide("s01", "media/a.png", "media/vo.wav", "00:02.05", "01:18.20")
    assert s.tin == approx(2.05)
    assert s.tout == approx(78.20)


def test_with_no_out_the_words_run_as_long_as_the_picture_does():
    s = Shot.parse({"id": "s01", "src": "media/a.png",
                    "voice": "media/vo.wav", "in": 5.0, "duration": 10.0}, 0)
    assert s.tout == approx(15.0)


def test_a_still_with_no_voice_is_exactly_what_it_was():
    s = Shot.parse({"src": "media/a.png", "duration": 4.5}, 0)
    assert s.voice is None
    assert s.duration == approx(4.5)
    assert s.tout is None


def test_a_clip_is_untouched_by_any_of_this():
    s = Shot.parse({"src": "media/x.mp4", "in": 1.0, "out": 5.0,
                    "speed": 1.2}, 0)
    assert s.kind == "video"
    assert s.voice is None
    assert s.duration == approx(4.0 / 1.2)


# --------------------------------------------------------------------------
# Refused before the render, with a message that says what to fix
# --------------------------------------------------------------------------

def test_a_voice_file_that_is_not_there_is_named(tmp_path):
    (tmp_path / "a.png").write_bytes(b"")
    f = Film(root=tmp_path,
             shots=[slide("s01", "a.png", "gone.wav", 1.0, 3.0)])
    with pytest.raises(SystemExit) as e:
        f.validate()
    assert "gone.wav" in str(e.value)
    assert "s01" in str(e.value)


def test_words_that_end_before_they_start_are_refused(tmp_path):
    (tmp_path / "a.png").write_bytes(b"")
    (tmp_path / "vo.wav").write_bytes(b"")
    f = Film(root=tmp_path,
             shots=[slide("s01", "a.png", "vo.wav", 9.0, 4.0)])
    with pytest.raises(SystemExit) as e:
        f.validate()
    assert "s01" in str(e.value)


# --------------------------------------------------------------------------
# Where the sound goes: the specs list build_soundtrack works from
# --------------------------------------------------------------------------

def here(shot):
    """Stand-in for the disk: every source carries sound."""
    return Path(shot.voice or shot.src)


def test_each_slide_puts_its_own_words_at_its_own_place_in_the_film():
    film = Film(fps=24, shots=[
        slide("s01", "media/a.png", "media/vo.wav", 2.0, 8.0),
        slide("s02", "media/b.png", "media/vo.wav", 9.5, 20.0),
    ])
    specs = speech_specs(film, 24, here)
    assert len(specs) == 2
    src1, start1, end1, delay1, speed1 = specs[0]
    _src2, start2, end2, delay2, _speed2 = specs[1]
    assert src1.name == "vo.wav"
    assert (start1, end1) == (approx(2.0), approx(8.0))
    assert delay1 == 0
    assert speed1 == 1.0
    # The second slide starts where the first one's picture ends, counted
    # in whole frames like everything else -- 6.4s is 154 frames at 24.
    assert (start2, end2) == (approx(9.5), approx(20.0))
    assert delay2 == approx(154 / 24 * 1000, abs=1)


def test_a_slide_with_no_voice_only_takes_up_time():
    film = Film(fps=24, shots=[
        Shot.parse({"src": "analysis/title.jpg", "duration": 2.0}, 0),
        slide("s02", "media/a.png", "media/vo.wav", 0.0, 5.0),
    ])
    specs = speech_specs(film, 24, lambda s: here(s) if s.voice else None)
    assert len(specs) == 1
    assert specs[0][3] == approx(2000, abs=1)     # after the silent card


def test_a_clip_and_a_slide_sit_on_the_same_timeline():
    film = Film(fps=24, shots=[
        Shot.parse({"id": "s01", "src": "media/x.mp4", "in": 10.0,
                    "out": 14.0}, 0),
        slide("s02", "media/a.png", "media/vo.wav", 1.0, 6.0),
    ])
    specs = speech_specs(film, 24, here)
    assert [s[0].name for s in specs] == ["x.mp4", "vo.wav"]
    assert specs[0][1] == approx(10.0)            # the clip's own clock
    assert specs[1][3] == approx(4000, abs=1)     # the slide, after it


def test_turning_off_clip_sound_does_not_silence_the_narration():
    """`keep_clip_audio` is about speech recorded in your video clips. A
    slide's `voice:` is the narration, which is not that."""
    film = Film(fps=24, keep_clip_audio=False, shots=[
        Shot.parse({"id": "s01", "src": "media/x.mp4", "in": 0.0,
                    "out": 4.0}, 0),
        slide("s02", "media/a.png", "media/vo.wav", 1.0, 6.0),
    ])
    specs = speech_specs(film, 24, here)
    assert [s[0].name for s in specs] == ["vo.wav"]


def test_a_film_wide_narration_still_plays_under_everything(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "vo.wav").write_bytes(b"")
    film = Film(fps=24, root=tmp_path, audio="media/vo.wav", audio_offset=2.0,
                shots=[Shot.parse({"src": "media/a.png",
                                   "duration": 5.0}, 0)])
    specs = speech_specs(film, 24, lambda s: None)
    assert len(specs) == 1
    _src, start, end, delay, _speed = specs[0]
    # A wait of two seconds, not two seconds cut off the front -- see
    # test_the_narration_offset_is_a_wait_not_a_cut.py.
    assert (start, end, delay) == (approx(0.0), None, 2000)


# --------------------------------------------------------------------------
# The words on screen: captions fitted through the voice file
# --------------------------------------------------------------------------

def test_captions_land_on_the_slide_whose_words_they_are():
    film = Film(shots=[
        slide("s01", "media/a.png", "media/vo.wav", 0.0, 10.0),
        slide("s02", "media/b.png", "media/vo.wav", 10.0, 20.0),
    ])
    source = voice_mod.VoiceSource(film.resolve("media/vo.wav"), "vo.wav",
                                   ["media/vo.wav"])
    placed, _ = caption_fit.fit_per_clip(film, source, [
        Line("first picture", 1.0, 4.0),
        Line("second picture", 12.0, 15.0),
    ])
    assert [c.text for c in placed["s01"]] == ["first picture"]
    assert [c.text for c in placed["s02"]] == ["second picture"]
    # On the slide's own clock: 12.0 on the narration is 2.0 into s02.
    assert placed["s02"][0].at == approx(2.0)


def test_two_slides_on_one_picture_still_get_their_own_words():
    """More paragraphs than pictures: the last picture is used twice,
    and matching on the PICTURE would put both captions on both."""
    film = Film(shots=[
        slide("s01", "media/a.png", "media/vo.wav", 0.0, 5.0),
        slide("s02", "media/a.png", "media/vo.wav", 6.0, 11.0),
    ])
    source = voice_mod.VoiceSource(film.resolve("media/vo.wav"), "vo.wav",
                                   ["media/vo.wav"])
    placed, _ = caption_fit.fit_per_clip(film, source, [
        Line("early", 1.0, 3.0), Line("late", 7.0, 9.0)])
    assert [c.text for c in placed["s01"]] == ["early"]
    assert [c.text for c in placed["s02"]] == ["late"]


def test_the_narration_of_a_slide_film_is_a_per_slide_source(tmp_path):
    """Not a global one. A global source is matched against the FILM's
    clock, and a slide film's narration is not on that clock -- its
    pieces are scattered across the shots that quote them."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "voiceover_20260917-105656.wav").write_bytes(b"")
    (media / "a.png").write_bytes(b"")
    film = Film(root=tmp_path, shots=[
        slide("s01", "media/a.png", "media/voiceover_20260917-105656.wav",
              0.0, 5.0)])
    sources = voice_mod.voice_sources(tmp_path, film)
    assert len(sources) == 1
    assert sources[0].shot_srcs == ["media/voiceover_20260917-105656.wav"]


def test_without_slides_the_narration_is_global_as_before(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "voiceover.wav").write_bytes(b"")
    film = Film(root=tmp_path, shots=[
        Shot.parse({"src": "media/a.png", "duration": 4.0}, 0)])
    assert voice_mod.voice_sources(tmp_path, film)[0].shot_srcs == []
    assert voice_mod.voice_sources(tmp_path)[0].shot_srcs == []


# --------------------------------------------------------------------------
# The bench rewrites the whole file, so it has to hand this back
# --------------------------------------------------------------------------

def test_the_bench_gives_a_slide_back_exactly_as_it_found_it(tmp_path):
    """`film edit` writes out the whole film.yaml on Save. It has no
    controls for a slide's words and must not be able to lose them --
    the same reason it carries `dissolve`, `fill` and from/to."""
    from ffilm import editor

    media = tmp_path / "media"
    media.mkdir()
    (media / "a.png").write_bytes(b"")
    (media / "vo.wav").write_bytes(b"")
    (tmp_path / "film.yaml").write_text(
        "fps: 24\n"
        "resolution: [1080, 1920]\n"
        "\n"
        "shots:\n"
        "  - id: s01\n"
        "    src: media/a.png\n"
        "    voice: media/vo.wav\n"
        '    in: "00:02.05"\n'
        '    out: "00:18.20"\n'
        "    move: drift_left\n", encoding="utf-8")

    film = Film.load(tmp_path / "film.yaml")
    state = editor.state(tmp_path)
    (tmp_path / "film.yaml").write_text(editor.dump(tmp_path, state),
                                        encoding="utf-8")
    after = Film.load(tmp_path / "film.yaml")

    assert after.shots[0].voice == film.shots[0].voice
    assert after.shots[0].tin == approx(film.shots[0].tin)
    assert after.shots[0].tout == approx(film.shots[0].tout)
    assert after.shots[0].duration == approx(film.shots[0].duration)


# --------------------------------------------------------------------------
# What `film check` may no longer say
# --------------------------------------------------------------------------

def test_a_slide_film_is_never_told_its_narration_will_be_cut_off():
    """checks.narration_note is about `audio:`, which plays flat under
    the whole film and is trimmed to it. A slide's words end where its
    `out:` says, so there is nothing to run out of."""
    film = Film(shots=[slide("s01", "media/a.png", "media/vo.wav",
                             0.0, 300.0)])
    assert film.audio is None
    assert checks.narration_notes(film) == []
