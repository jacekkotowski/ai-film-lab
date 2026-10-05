"""
A film a little over its limit is fitted by one small rise of `speed:`,
and every caption stays on the word it was written for.

Why this is a command and not a digit to change by hand: a caption's
`at`, `dur` and `words` are stored in FILM seconds, already divided by
the shot's speed when `film caption` wrote them (caption_fit._place).
Change `speed:` 1.2 -> 1.24 and the voice moves, the captions do not: a
caption 28 s into a shot lands about 0.9 s late, and a caption pushed
past the end of its shot is trimmed with no warning (spec.py). Going from
speed a to b multiplies every film time inside that shot by a / b. That
is exact, and needs no new transcription.
"""

import pytest

from ffilm.checks import speed_to_fit
from ffilm.slides import refit_speed
from ffilm.spec import Film

YAML = """\
# Written by `film init`. Everything here is a starting point.
fps: 24

shots:

  - id: s00
    src: analysis/title.jpg
    duration: 2.0
    move: static

  - id: s01
    src: media/rec_1.mp4
    in: "00:01.00"
    out: "01:01.00"
    speed: 1.2              # 1.0 is the speed you actually spoke at
    move: static
    note: "kept whole"
    captions:
      - text: "one"
        at: 0.00
        dur: 2.50
        words: [0.00, 0.50, 1.00]
      - text: "two"
        at: 28.00
        dur: 3.00
        words: [0.00, 1.20, 2.40]

  - id: s02
    src: media/pic.png
    voice: media/voiceover_1.wav
    in: "00:00.00"
    out: "01:00.00"
    speed: 1.2              # 1.0 is the speed you actually read at
    move: columns
    captions:
      - text: "three"
        at: 10.00
        dur: 2.00
        words: [0.00, 1.00]

  - id: s03
    src: media/other.jpg
    duration: 5.0
    move: static

# 4 shots.
"""

LIMIT = 180.0


def load(tmp_path, text):
    yml = tmp_path / "film.yaml"
    yml.write_text(text, encoding="utf-8")
    return Film.load(yml, check_files=False)


def source_moment(shot, cap, offset=0.0):
    """Where in the recording a caption sits: film time x speed."""
    return (cap.at + offset) * shot.speed


def test_the_speed_found_is_the_smallest_that_fits(tmp_path):
    film = load(tmp_path, YAML)
    assert film.duration > 100          # sanity: 50 + 50 + 0.4 + 7
    target = film.duration - 3.0
    s = speed_to_fit(film, target, max_speed=1.5)
    assert s is not None and s > 1.2

    fitted = load(tmp_path, refit_speed(YAML, film, s))
    assert fitted.duration <= target + 1e-6
    # ... and the step below it would not have fitted
    lower = load(tmp_path, refit_speed(YAML, film, round(s - 0.01, 2)))
    assert lower.duration > target


def test_a_film_that_already_fits_is_left_alone(tmp_path):
    film = load(tmp_path, YAML)
    assert speed_to_fit(film, film.duration + 5, max_speed=1.5) == pytest.approx(1.2)


def test_past_the_ceiling_it_says_so_instead_of_speeding_up(tmp_path):
    film = load(tmp_path, YAML)
    assert speed_to_fit(film, film.duration - 3.0, max_speed=1.21) is None


def test_a_target_the_fixed_parts_alone_overrun_is_refused(tmp_path):
    film = load(tmp_path, YAML)
    assert speed_to_fit(film, 5.0, max_speed=9.0) is None


def test_every_caption_stays_on_the_same_moment_of_the_recording(tmp_path):
    film = load(tmp_path, YAML)
    s = speed_to_fit(film, film.duration - 3.0, max_speed=1.5)
    fitted = load(tmp_path, refit_speed(YAML, film, s))

    for before, after in zip(film.shots, fitted.shots):
        if not before.captions:
            continue
        assert after.speed == pytest.approx(s)
        for a, b in zip(before.captions, after.captions):
            assert source_moment(after, b) == pytest.approx(
                source_moment(before, a), abs=0.01)
            assert (b.at + b.dur) * after.speed == pytest.approx(
                (a.at + a.dur) * before.speed, abs=0.01)
            for wa, wb in zip(a.words, b.words):
                assert source_moment(after, b, wb) == pytest.approx(
                    source_moment(before, a, wa), abs=0.01)


def test_a_picture_with_a_fixed_duration_keeps_its_length(tmp_path):
    film = load(tmp_path, YAML)
    s = speed_to_fit(film, film.duration - 3.0, max_speed=1.5)
    fitted = load(tmp_path, refit_speed(YAML, film, s))
    assert fitted.shots[0].duration == pytest.approx(2.0)
    assert fitted.shots[3].duration == pytest.approx(5.0)


def test_nothing_else_in_the_file_is_touched(tmp_path):
    film = load(tmp_path, YAML)
    out = refit_speed(YAML, film, 1.25)
    assert "# Written by `film init`" in out
    assert "# 4 shots." in out
    assert '    note: "kept whole"' in out
    assert "# 1.0 is the speed you actually spoke at" in out
    assert out.count("speed:") == 2
    # captions' text and pos are as they were
    assert 'text: "two"' in out


def test_a_caption_it_cannot_find_is_refused_not_guessed_at(tmp_path):
    # flow-style caption: parses, but its `at:` is not a line we can scale
    odd = YAML.replace(
        '      - text: "one"\n        at: 0.00\n        dur: 2.50\n'
        '        words: [0.00, 0.50, 1.00]\n',
        '      - {text: "one", at: 0.0, dur: 2.5}\n')
    assert odd != YAML
    film = load(tmp_path, odd)
    with pytest.raises(ValueError):
        refit_speed(odd, film, 1.25)
