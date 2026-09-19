"""
A narration stopped before the last picture is put aside, not used.

Found 2026-09-19 on German Forgotten Bauhaus Hope: the narration window
opened on the wrong words, so it was closed after the second picture.
Closing saved the 22.5 s take, and from then on it WAS the narration --
the guide moved on to "say a few closing words", over a film narrated
for two pictures out of ten.

And the wrong words themselves: the narration window read script.txt,
which is where the camera window had saved the intro just said. The
two are different texts, so they are now different files.
"""

from ffilm import booth
from ffilm.guide import so_far
from ffilm.record import narration_finished


def test_a_take_that_reached_the_last_picture_is_the_narration():
    assert narration_finished(presses=9, pictures=10)


def test_a_take_closed_on_picture_two_of_ten_is_not():
    assert not narration_finished(presses=1, pictures=10)


def test_a_single_picture_is_finished_by_stopping():
    assert narration_finished(presses=0, pictures=1)


def test_the_narration_window_does_not_show_the_words_said_to_the_camera(
        tmp_path):
    (tmp_path / "script.txt").write_text("Hello, this is the intro.",
                                         encoding="utf-8")
    assert booth.read_script(tmp_path, None, voice=True) == ""
    assert "intro" in booth.read_script(tmp_path, None)


def test_the_narration_window_keeps_its_own_words(tmp_path):
    booth.save_script(booth.script_path(tmp_path, voice=True),
                      "Picture one.\n\nPicture two.")
    assert "Picture two" in booth.read_script(tmp_path, None, voice=True)
    assert not (tmp_path / "script.txt").exists()


# "I did not know where I am" -- the guide now says what is already there.

def test_the_guide_says_what_has_been_recorded_so_far():
    line = so_far(["1_.jpg", "2_.jpg", "rec_20260919-122456.mp4",
                   "voiceover_20260919-133551.wav",
                   "voiceover_20260919-133551.cues.json"])
    assert "2 photos" in line
    assert "opening talk (12:24)" in line
    assert "narration (13:35)" in line


def test_a_take_after_the_narration_is_called_the_closing_talk():
    line = so_far(["1_.jpg", "voiceover_20260919-133551.wav",
                   "rec_20260919-140000.mp4"])
    assert "closing talk (14:00)" in line


def test_nothing_recorded_yet_says_so():
    assert "no narration yet" in so_far(["1_.jpg"])
