"""
"So far" lists what you recorded in the order you recorded it.

The line exists so that somebody coming back to a film can see what is
already done. It put the narration last no matter when it was made, and
the takes in the middle -- so an evening's work came out as

    5 photos | opening talk (19:53) | closing talk (20:00) | narration (19:58)

which reads as though the narration were recorded after the closing
words. Found 2026-09-20 on 1930s Austria Had Photoshop, where it made
Jacek doubt a session that was entirely correct: 19:53 really is before
19:58, so that take really is the opening, and 20:00 really is after it.

The labels were right and only the order they were printed in was
wrong, which is the worst version of this -- nothing downstream is
broken, so nothing but a person reading it can catch it.

Pure: names only, no files.
"""

from ffilm.guide import so_far

EVENING = ["1_xray.jpg", "2_roentgen.png", "3_portrait_process.png",
           "4_eye.png", "5_example.jpg",
           "rec_20260920-195315.mp4",
           "voiceover_20260920-195800.wav",
           "rec_20260920-200039.mp4"]


def order_of(names):
    """The labels, without the photo count, in the order printed."""
    return [p.strip() for p in so_far(names).replace("So far:", "").split("|")
            ][1:]


def test_the_narration_sits_where_it_was_recorded():
    assert order_of(EVENING) == ["opening talk (19:53)",
                                 "narration (19:58)",
                                 "closing talk (20:00)"]


def test_a_narration_recorded_last_really_is_printed_last():
    names = ["a.jpg", "rec_20260920-195315.mp4",
             "voiceover_20260920-201000.wav"]
    assert order_of(names) == ["opening talk (19:53)",
                               "narration (20:10)"]


def test_the_photos_still_come_first():
    assert so_far(EVENING).startswith("So far:  5 photos")


def test_nothing_recorded_yet_still_says_so():
    assert so_far(["a.jpg"]) == "So far:  1 photo  |  no narration yet"


def test_takes_with_no_narration_keep_their_own_order():
    names = ["a.jpg", "rec_20260920-200039.mp4", "rec_20260920-195315.mp4"]
    assert order_of(names) == ["talk to the camera (19:53)",
                               "talk to the camera (20:00)",
                               "no narration yet"]
