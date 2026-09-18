"""
Pressing Next in the recording window marks where the picture changes.

Jacek asked for it on 2026-09-18: "I should see the picture I am
describing, press a button, go to the next picture, describe it." Until
then `film record --voice` opened the booth with an empty black panel
where the camera would have been, scrolled the whole script as one text,
and left `init` to guess where one picture ended and the next began.

Now, in voice mode, the booth shows one picture and its paragraph at a
time, and SPACE goes to the next one. Each press is noted on the
AUDIO's own clock: the microphone meter is a second output of the same
input stream, through ffmpeg's `ebur128`, and every line it prints
starts with `t:`, the stream's time. Measured on test_story's own
narration: 595 lines for 59.5 s, one every 0.1 s, the last reading
59.5. A press stamped with the latest `t:` is where it happened in the
wav, whatever the microphone took to wake up. The computer's wall clock
would have been off by that start-up delay.

The presses are written beside the take, `voiceover_....cues.json`, and
`init` cuts the narration there.

The window itself cannot be tested. Every decision in it is here.
"""

import json

from pytest import approx

from ffilm import booth, record


# --------------------------------------------------------------------------
# The audio's own clock, read off the meter
# --------------------------------------------------------------------------

LINE = (b"[Parsed_ebur128_0 @ 00000255e2ccc100] t: 9.899979   "
        b"TARGET:-23 LUFS    M: -26.3 S: -32.2     I: -27.0 LUFS       "
        b"LRA:   8.7 LU")


def test_the_time_is_read_off_a_meter_line():
    assert booth.audio_clock(LINE) == approx(9.899979)


def test_target_is_not_mistaken_for_the_time():
    """`TARGET:` ends in a T and a colon. It is not the time."""
    assert booth.audio_clock(b"TARGET:-23 LUFS    M: -26.3") is None


def test_any_other_line_has_no_time():
    assert booth.audio_clock(b"Press [q] to stop") is None


# --------------------------------------------------------------------------
# From presses to cues
# --------------------------------------------------------------------------

def test_presses_become_cues_on_the_take():
    assert record.clean_cues([17.9, 38.6], 59.5) == [17.9, 38.6]


def test_a_press_in_the_last_half_second_is_dropped():
    """That is somebody reaching for Stop, not moving to a picture that
    would then be on screen for no time at all."""
    assert record.clean_cues([17.9, 59.2], 59.5) == [17.9]


def test_a_double_press_counts_once():
    assert record.clean_cues([17.9, 17.9, 38.6], 59.5) == [17.9, 38.6]


def test_a_press_before_the_audio_started_is_dropped():
    assert record.clean_cues([0.0, 17.9], 59.5) == [17.9]


def test_the_audio_clock_is_trusted_when_there_is_one():
    assert record.press_times([(17.9, 1000.0)], 1050.0, 59.5) == [17.9]


def test_with_no_meter_reading_the_press_is_counted_back_from_stop():
    """Stopped 41.6 s after the press, in a 59.5 s take: 17.9 s in."""
    assert record.press_times([(0.0, 1000.0)], 1041.6, 59.5) == [approx(17.9)]


def test_a_dropped_press_does_not_move_the_pictures_after_it():
    """The first press came before any sound and is dropped. Picture 3
    must still be the one after the second press, not picture 2."""
    cues, pictures = record.settle_cues(
        [0.0, 38.6], 59.5, ["media/1.png", "media/2.png", "media/3.png"])
    assert cues == [38.6]
    assert pictures == ["media/1.png", "media/3.png"]


def test_the_cues_file_sits_beside_its_take(tmp_path):
    take = tmp_path / "voiceover_20260919-101500.wav"
    assert record.cues_path(take).name == "voiceover_20260919-101500.cues.json"


def test_what_is_written_is_what_is_read_back(tmp_path):
    take = tmp_path / "voiceover_20260919-101500.wav"
    record.write_cues(take, [17.9, 38.6],
                      ["media/1a.png", "media/2b.png", "media/3c.png"])
    got = record.read_cues(take)
    assert got["cues"] == [17.9, 38.6]
    assert got["pictures"] == ["media/1a.png", "media/2b.png", "media/3c.png"]
    # Readable by a person, not one long line.
    assert "\n" in record.cues_path(take).read_text(encoding="utf-8")


def test_a_take_with_no_cues_file_has_none(tmp_path):
    assert record.read_cues(tmp_path / "voiceover.wav") is None


def test_a_broken_cues_file_is_treated_as_none(tmp_path):
    take = tmp_path / "voiceover.wav"
    record.cues_path(take).write_text("{not json", encoding="utf-8")
    assert record.read_cues(take) is None


def test_cues_that_are_not_numbers_are_treated_as_none(tmp_path):
    take = tmp_path / "voiceover.wav"
    record.cues_path(take).write_text(json.dumps({"cues": ["x"]}),
                                      encoding="utf-8")
    assert record.read_cues(take) is None


def test_the_cues_file_is_never_taken_for_the_narration(tmp_path):
    """Found by the first end-to-end run: `voice_sources` took any file
    whose name starts `voiceover`, and `voiceover_....cues.json` sorts
    before `voiceover_....wav`. So the speech model was handed the JSON
    and `film caption` stopped with "Invalid data found"."""
    from ffilm import voice

    media = tmp_path / "media"
    media.mkdir()
    take = media / "voiceover_20260919-101500.wav"
    take.write_bytes(b"")
    record.write_cues(take, [17.9], ["media/a.png", "media/b.png"])
    sources = voice.voice_sources(tmp_path)
    assert [s.label for s in sources] == [take.name]


# --------------------------------------------------------------------------
# What the window shows
# --------------------------------------------------------------------------

def test_a_tall_picture_fits_the_height_of_its_box():
    assert booth.fit_size(900, 1600, 800, 600) == (338, 600)


def test_a_wide_picture_fits_the_width_of_its_box():
    assert booth.fit_size(1600, 900, 800, 600) == (800, 450)


def test_a_small_picture_is_not_blown_up_past_twice_its_size():
    """A thumbnail-sized picture scaled to a whole screen is a smear."""
    assert booth.fit_size(100, 100, 800, 600) == (200, 200)


def test_the_window_says_which_picture_this_is():
    assert booth.step_caption(1, 3) == "picture 2 of 3"


def test_the_button_says_next_until_the_last_picture():
    assert "Next" in booth.next_label(0, 3)
    assert "Next" in booth.next_label(1, 3)
    assert "Finish" in booth.next_label(2, 3)


def test_the_first_screen_says_what_next_does():
    said = booth.compose_hint(voice_only=True).lower()
    assert "paragraph" in said
    assert "space" in said
