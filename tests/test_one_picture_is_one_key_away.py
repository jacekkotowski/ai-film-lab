"""
One picture's words are one key away.

Asked 2026-09-24: "I did not see the button." Saying the words over one
picture again (fd18000) was built, but offered as the eighth numbered
line of the menu, worded like the line above it. The moment you want it
is after watching a draft, stressed, looking for the fix for one fluffed
sentence -- so it is a fixed letter, P, first on the line of keys that
is always shown, and it is not also a numbered line.
"""

from ffilm.guide import can_redo_one_picture, recording_doors, standing_keys


def test_p_is_first_on_the_key_line_when_a_picture_can_be_said_again():
    keys = standing_keys(gear_ok=True, others=True, claude=True,
                         one_picture=True)
    assert keys[0].startswith("P ")
    assert keys[-1].startswith("Q ")


def test_no_p_when_there_is_nothing_to_say_again():
    keys = standing_keys(gear_ok=True, others=True, claude=True,
                         one_picture=False)
    assert not any(k.startswith("P ") for k in keys)


def test_the_other_keys_are_unchanged():
    keys = standing_keys(gear_ok=True, others=True, claude=True,
                         one_picture=False)
    assert keys == ["M microphone/camera", "N new film", "F other film",
                    "C tell Claude", "Q quit"]


def test_a_picture_can_be_said_again_once_there_is_a_narrated_edit():
    names = ["1_a.jpg", "voiceover_20260924-101945.wav"]
    assert can_redo_one_picture(names, has_edit=True, windows=True)


def test_not_before_the_narration_is_cut_into_an_edit():
    names = ["1_a.jpg", "voiceover_20260924-101945.wav"]
    assert not can_redo_one_picture(names, has_edit=False, windows=True)


def test_not_without_a_narration():
    assert not can_redo_one_picture(["1_a.jpg"], has_edit=True, windows=True)


def test_not_where_the_window_cannot_open():
    names = ["1_a.jpg", "voiceover_20260924-101945.wav"]
    assert not can_redo_one_picture(names, has_edit=True, windows=False)


def test_it_is_not_also_a_numbered_line():
    doors = recording_doors(["1_a.jpg", "voiceover_20260924-101945.wav"],
                            [], windows=True)
    assert not any("--picture" in d.args for d in doors)
