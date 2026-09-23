"""
A camera take is heard when the lips move.

Found 2026-09-23 (docs/OPEN.md #1): the microphone starts 0.4-0.9 s after
the camera, but both are stamped from 0 in the file, so the voice ran
ahead of the lips. speech_specs now reads the sound that late, and a
slide's narration is left exactly as it was.
"""

from pathlib import Path

from ffilm.audio import speech_specs
from ffilm.spec import Film, Shot


def film_of(*shots):
    f = Film()
    f.root = Path(".")
    f.shots = list(shots)
    return f


def take(tin=1.2, tout=14.1, speed=1.2):
    return Shot.parse({"src": "media/0_rec_20260923-123013.mp4",
                       "in": tin, "out": tout, "speed": speed}, 0)


def test_the_sound_of_a_late_take_is_read_that_much_earlier():
    f = film_of(take())
    src = Path("media/0_rec_20260923-123013.mp4")
    plain = speech_specs(f, 24, lambda s: src)[0]
    fixed = speech_specs(f, 24, lambda s: src, late_for=lambda p: 0.58)[0]
    assert abs(fixed[1] - (plain[1] - 0.58)) < 1e-9     # start
    assert abs(fixed[2] - (plain[2] - 0.58)) < 1e-9     # end
    assert fixed[3] == plain[3]                          # same place in film
    assert fixed[4] == plain[4]                          # same speed


def test_a_take_used_from_its_first_second_waits_for_its_sound():
    f = film_of(take(tin=0.2))
    src = Path("media/0_rec_20260923-123013.mp4")
    s = speech_specs(f, 24, lambda sh: src, late_for=lambda p: 0.58)[0]
    assert s[1] == 0.0
    assert s[3] == round(0.38 / 1.2 * 1000)             # silence first


def test_the_slides_narration_is_not_moved():
    slide = Shot.parse({"src": "media/1_a.jpg",
                        "voice": "media/voiceover_x.wav",
                        "in": 5.0, "out": 9.0}, 0)
    f = film_of(slide)
    wav = Path("media/voiceover_x.wav")
    a = speech_specs(f, 24, lambda s: wav)[0]
    b = speech_specs(f, 24, lambda s: wav, late_for=lambda p: 0.58)[0]
    assert a == b
