"""
One picture is a numbered line and a button.

Asked 2026-09-28: "there was no button or command to try." The key P
(c52336d) was on the line of letters under the menu, and he did not see
it there either. The numbered line that says the words over ALL the
pictures again was right above it, and looked like the thing to press.

So one picture is offered three ways now: the key P stays, a numbered
line comes back -- worded so it cannot be read as the one above it --
and the recording window has a button on its first screen that lists
the pictures and opens the window again on the one picked.
"""

from ffilm.booth import one_picture_choices
from ffilm.guide import recording_doors

NAMES = ["1_a.jpg", "2_b.jpg", "voiceover_20260924-101945.wav"]


def _one(doors):
    return [d for d in doors if "--picture" in d.args]


def test_a_narrated_edit_offers_one_picture_as_a_numbered_line():
    doors = recording_doors(NAMES, [], windows=True, has_edit=True)
    assert len(_one(doors)) == 1


def test_the_line_says_one_and_cannot_be_read_as_all_of_them():
    door = _one(recording_doors(NAMES, [], windows=True, has_edit=True))[0]
    everything = [d for d in recording_doors(NAMES, [], windows=True,
                                             has_edit=True)
                  if d.args == ["record", "--voice"]][0]
    assert "ONE" in door.title
    assert door.title.split()[:4] != everything.title.split()[:4]


def test_it_comes_straight_after_all_of_them():
    shapes = [d.args for d in recording_doors(NAMES, [], windows=True,
                                              has_edit=True)]
    i = shapes.index(["record", "--voice"])
    assert shapes[i + 1] == ["record", "--voice", "--picture"]


def test_the_line_is_there_before_the_narration_is_cut_into_an_edit():
    # 2026-09-29: the narration was said 3 times before any edit existed,
    # and the line was hidden all that time. `record --picture` now
    # builds the edit first when there is none.
    assert _one(recording_doors(NAMES, [], windows=True, has_edit=False))


def test_no_line_without_a_narration():
    assert not _one(recording_doors(["1_a.jpg"], [], windows=True,
                                    has_edit=True))


def test_no_line_where_the_window_cannot_open():
    assert not _one(recording_doors(NAMES, [], windows=False, has_edit=True))


MENU = ["  1  a.jpg  'In Plato'", "  2  b.jpg  'Religions gave'"]


def test_the_window_lists_the_pictures_when_reading_over_all_of_them():
    assert one_picture_choices(MENU, voice_only=True,
                               one_already=False) == MENU


def test_no_button_when_the_window_is_already_on_one_picture():
    assert one_picture_choices(MENU, voice_only=True,
                               one_already=True) is None


def test_no_button_in_front_of_the_camera():
    assert one_picture_choices(MENU, voice_only=False,
                               one_already=False) is None


def test_the_button_is_there_before_the_edit_once_there_is_a_narration():
    # 2026-09-29, It Reads Us: recorded before any edit, never saw it.
    # [] = the button, whose screen cuts the narration first.
    assert one_picture_choices([], voice_only=True, one_already=False,
                               has_narration=True) == []


def test_no_button_before_anything_was_said():
    assert one_picture_choices([], voice_only=True,
                               one_already=False) is None
