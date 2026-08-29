"""
Captions on screen, and knowing what a file is.

Same rule as the other test file: these are all things that went wrong in
front of somebody, and they are all cheap to check.
"""

from PIL import Image, ImageDraw

from ffilm import kinds
from ffilm.caption_fit import fit_global
from ffilm.render import CAPTION_MAX_WIDTH, fit_caption, load_font, wrap_to_width
from ffilm.spec import Caption, Film, Shot
from ffilm.voice import Line


# --------------------------------------------------------------------------
# Captions have to fit inside the frame
# --------------------------------------------------------------------------

LONG = "This is where my grandfather used to work every single morning before dawn"


def draw():
    return ImageDraw.Draw(Image.new("RGBA", (8, 8)))


def test_a_whisper_length_line_wraps_inside_a_vertical_frame():
    """Unwrapped, this was 2728px of text centred in a 1080px frame -- it
    did not clip, it ran off both edges."""
    d, w = draw(), 1080
    font, lines = fit_caption(d, LONG, int(1920 * 0.042), None,
                              w * CAPTION_MAX_WIDTH)
    assert len(lines) > 1
    # Measured against the FRAME, not against the constant under test --
    # otherwise widening the constant would widen the assertion with it
    # and the test would approve of text running off the screen.
    assert max(d.textlength(ln, font=font) for ln in lines) <= w


def test_a_short_caption_stays_on_one_line():
    d = draw()
    _font, lines = fit_caption(d, "Kolobrzeg, November", 45, None, 1600)
    assert lines == ["Kolobrzeg, November"]


def test_wrapping_keeps_every_word_in_order():
    d = draw()
    lines = wrap_to_width(d, LONG, load_font(60), 500)
    assert " ".join(lines).split() == LONG.split()


def test_a_newline_you_typed_is_respected():
    d = draw()
    assert len(wrap_to_width(d, "one\ntwo", load_font(20), 10_000)) == 2


# --------------------------------------------------------------------------
# Putting a transcript line on the right shot
# --------------------------------------------------------------------------


def film_of(*durations):
    f = Film()
    f.shots = [Shot(src=f"media/{i}.mp4", kind="video", duration=d,
                    id=f"s{i + 1:02d}") for i, d in enumerate(durations)]
    return f


def test_lines_land_on_the_shot_they_were_said_over():
    placed, _ = fit_global(film_of(5.0, 5.0),
                           [Line("first", 1.0, 3.0), Line("second", 6.0, 8.0)])
    assert placed["s01"][0].text == "first"
    assert placed["s02"][0].text == "second"


def test_several_lines_can_share_one_shot():
    """Only one caption per shot was landing, and the rest vanished."""
    placed, _ = fit_global(film_of(20.0),
                           [Line("a", 0.5, 2.0), Line("b", 4.0, 6.0),
                            Line("c", 9.0, 11.0)])
    assert len(placed["s01"]) == 3


def test_a_caption_never_runs_past_the_end_of_its_shot():
    placed, _ = fit_global(film_of(5.0), [Line("late", 4.0, 12.0)])
    cap = placed["s01"][0]
    assert cap.at + cap.dur <= 5.0 + 1e-6


def test_hitting_the_readability_cap_is_not_a_warning():
    """Being clipped at MAX_CAPTION_SECONDS is the design. Warning about it
    sent people off lengthening shots that were the right length."""
    _placed, warnings = fit_global(film_of(60.0), [Line("x", 0.0, 30.0)])
    assert warnings == []


def test_running_out_of_shot_IS_a_warning():
    _placed, warnings = fit_global(film_of(5.0), [Line("x", 4.5, 9.0)])
    assert warnings


# --------------------------------------------------------------------------
# Nothing that is not a plain YAML value may reach film.yaml
# --------------------------------------------------------------------------


def test_numpy_timestamps_become_plain_floats():
    """faster-whisper hands back numpy scalars. They behave like floats
    right up until yaml.dump writes one as !!python/object/apply and the
    film.yaml can no longer be read at all."""
    import numpy as np
    ln = Line("hello", np.float32(1.25), np.float64(3.5))
    assert type(ln.start) is float and type(ln.end) is float
    assert isinstance(ln.text, str)


def test_a_film_with_captions_survives_a_round_trip(tmp_path):
    import yaml
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "a.jpg").write_bytes(b"not really a jpg")
    (tmp_path / "film.yaml").write_text(yaml.safe_dump({
        "fps": 24, "resolution": [1080, 1920],
        "shots": [{"id": "s01", "src": "media/a.jpg", "duration": 4.0,
                   "captions": [{"text": "Kołobrzeg", "at": 0.5, "dur": 2.0}]}],
    }, allow_unicode=True), encoding="utf-8")
    film = Film.load(tmp_path / "film.yaml")
    assert film.shots[0].captions[0].text == "Kołobrzeg"


# --------------------------------------------------------------------------
# What counts as a photo, a clip, a track
# --------------------------------------------------------------------------


def test_file_kinds():
    assert kinds.is_video("a.MKV") and kinds.is_video("b.mov")
    assert kinds.is_still("c.HEIC") and kinds.is_still("d.jpg")
    assert kinds.is_audio("e.mp3")
    assert not kinds.is_media("notes.txt")


def test_the_shot_class_agrees_with_kinds():
    """Shot.VIDEO_EXT is used by film.yaml files in the wild."""
    assert Shot.VIDEO_EXT is kinds.VIDEO
    assert Shot.parse({"src": "media/x.mkv"}, 0).kind == "video"
    assert Shot.parse({"src": "media/x.jpg"}, 0).kind == "still"


def test_a_video_shot_gets_its_duration_from_in_and_out():
    s = Shot.parse({"src": "media/x.mp4", "in": "0:10", "out": "0:14.5"}, 0)
    assert s.duration == 4.5
