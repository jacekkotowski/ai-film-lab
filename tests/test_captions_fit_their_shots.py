"""
A caption that runs past the end of its shot.

This used to refuse the whole film. Not warn -- refuse: `film peek` on a
thirty-six second film stopped dead because one subtitle was 0.058
seconds too long, which is one and a half frames, which is nothing you
could see. The overrun had been put there by the toolkit's own rounding,
in three different places.

So there are two halves here. Nothing may WRITE a caption that overruns;
and if one turns up anyway -- hand-typed, or from a version of this
toolkit that had the bug -- it is trimmed to fit and the film renders.
"""

import pytest

from ffilm.caption_fit import MAX_CAPTION_SECONDS, _place
from ffilm.editor import dump
from ffilm.spec import Caption, Film, Shot
from ffilm.voice import Line


def film_of(*shots) -> Film:
    return Film(shots=list(shots))


def shot(dur, *caps, sid="s01") -> Shot:
    return Shot(src="media/a.jpg", duration=dur, id=sid,
                captions=[Caption(text=t, at=a, dur=d) for t, a, d in caps])


# --------------------------------------------------------------------------
# It is trimmed, not refused
# --------------------------------------------------------------------------

def test_a_caption_a_frame_and_a_half_too_long_does_not_stop_the_film():
    """The exact case: at 7.4 for 3.0 on a shot of 10.3416666s."""
    f = film_of(shot(10.341666666666667, ("you're waking your awakening", 7.4, 3.0)))
    f.trim_captions()
    c = f.shots[0].captions[0]
    assert c.at + c.dur <= f.shots[0].duration + 1e-9


def test_a_rounding_overrun_is_not_worth_telling_anybody_about():
    f = film_of(shot(10.341666666666667, ("a line", 7.4, 3.0)))
    assert f.trim_captions() == []


def test_a_caption_that_really_is_too_long_says_so():
    """Three seconds of a line you meant to be read will not be on
    screen. That is worth one printed line -- but still not a refusal."""
    f = film_of(shot(5.0, ("a long thought", 1.0, 7.0)))
    notes = f.trim_captions()
    assert len(notes) == 1 and "cut short" in notes[0]
    assert f.shots[0].captions[0].dur == 4.0


def test_a_caption_starting_after_the_shot_has_ended_is_not_shown():
    f = film_of(shot(5.0, ("too late", 6.0, 2.0)))
    notes = f.trim_captions()
    assert f.shots[0].captions[0].dur == 0.0
    assert "starts after the shot ends" in notes[0]


def test_a_caption_that_already_fits_is_left_exactly_alone():
    f = film_of(shot(10.0, ("fits", 1.0, 3.0)))
    assert f.trim_captions() == []
    c = f.shots[0].captions[0]
    assert (c.at, c.dur) == (1.0, 3.0)


def test_trimming_twice_changes_nothing_the_second_time():
    f = film_of(shot(5.0, ("a long thought", 1.0, 7.0)))
    f.trim_captions()
    assert f.trim_captions() == []


def test_the_things_that_still_refuse_a_film_still_refuse_it():
    """Trimming captions is not a licence to render anything at all. A
    shot pointing at a file that is not there cannot be drawn."""
    with pytest.raises(SystemExit):
        film_of(Shot(src="media/gone.jpg", duration=2.0, id="s01")).validate()
    with pytest.raises(SystemExit):
        film_of().validate()


# --------------------------------------------------------------------------
# Nothing may write one in the first place -- 1: `film caption`
# --------------------------------------------------------------------------

def placed(shot_len, start, dur, speed=1.0):
    """One transcript line onto one shot, on the clip's own clock."""
    warnings = []
    cap = _place("s01", 0.0, shot_len * speed,
                 Line(start=start, end=start + dur, text="said"),
                 warnings, speed)
    return cap, warnings


def test_a_placed_caption_never_runs_past_its_shot():
    """Awkward on purpose: every one of these lands where rounding `at`
    up and `dur` up independently would have overrun."""
    for shot_len in (10.341666666666667, 7.5583333, 6.2666667, 8.9333333):
        for start in (0.0, 1.005, 3.996, 7.3959, 7.404):
            cap, _ = placed(shot_len, start, 9.0)
            if cap is not None:
                assert cap.at + cap.dur <= shot_len + 1e-9, (shot_len, start)


def test_a_placed_caption_survives_being_written_at_two_decimals():
    """The numbers in film.yaml are what matters, not the ones in
    memory: they are what gets loaded back."""
    cap, _ = placed(10.341666666666667, 7.3959, 9.0)
    assert round(cap.at, 2) == cap.at
    assert round(cap.dur, 2) == cap.dur


def test_a_sped_up_shot_still_fits_its_captions():
    """speed 1.2 shortens the shot and the caption by different amounts,
    which is where the arithmetic used to come apart."""
    cap, _ = placed(10.341666666666667, 8.87, 4.0, speed=1.2)
    assert cap.at + cap.dur <= 10.341666666666667 + 1e-9


def test_a_line_with_no_room_left_is_dropped_not_squeezed():
    cap, warnings = placed(5.0, 4.8, 3.0)
    assert cap is None and "dropped" in warnings[0]


def test_a_long_line_is_still_capped_for_readability():
    cap, _ = placed(30.0, 0.0, 20.0)
    assert cap.dur <= MAX_CAPTION_SECONDS


# --------------------------------------------------------------------------
# Nothing may write one in the first place -- 2: the bench
# --------------------------------------------------------------------------

def bench_yaml(tmp_path, duration, at, dur):
    (tmp_path / "film.yaml").write_text("fps: 24\n", encoding="utf-8")
    return dump(tmp_path, {
        "fps": 24, "width": 1080, "height": 1920,
        "shots": [{"id": "s01", "src": "media/a.jpg", "kind": "still",
                   "duration": duration, "move": "static", "ease": "linear",
                   "amount": 1.0, "focus": [0.5, 0.5], "note": "",
                   "dissolve": 0.0, "fill": None, "frm": None, "to": None,
                   "captions": [{"text": "said", "at": at, "dur": dur,
                                 "pos": "bottom"}]}]})


def test_the_bench_cannot_save_a_film_it_could_not_load(tmp_path):
    """Dragging a shot shorter leaves the captions where they were. One
    click of Save used to write a film.yaml that then refused to open --
    and the bench is the tool somebody reaches for when they are already
    stuck."""
    out = bench_yaml(tmp_path, duration=10.34, at=7.35, dur=2.96)
    (tmp_path / "film.yaml").write_text(out, encoding="utf-8")
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "a.jpg").write_bytes(b"x")
    f = Film.load(tmp_path / "film.yaml")           # must not raise
    c = f.shots[0].captions[0]
    assert c.at + c.dur <= f.shots[0].duration + 1e-9


def test_the_bench_drops_a_caption_a_shot_no_longer_has_room_for(tmp_path):
    assert "said" not in bench_yaml(tmp_path, duration=2.0, at=5.0, dur=1.0)


def test_the_bench_still_writes_an_ordinary_caption_untouched(tmp_path):
    out = bench_yaml(tmp_path, duration=10.0, at=1.0, dur=3.0)
    assert "at: 1.0" in out and "dur: 3.0" in out
