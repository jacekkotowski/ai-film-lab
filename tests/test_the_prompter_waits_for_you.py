"""
The teleprompter waits for you.

It used to scroll at a fixed reading speed from the moment the camera
woke. Stop to think, or to say something twice, and the words ran on
without you -- and the next take began with finding your place.

Now it moves while you are talking and holds still when you stop. It
reads the loudness the recorder already measures for the mic meter; no
speech model, nothing new running beside the recording. It learns how
loud the room is on its own, so it works at any microphone gain, and
until it has heard the room it scrolls exactly as it always did.
"""

from ffilm.booth import VoiceFollow

ROOM, VOICE = -58.0, -28.0


def feed(follow, levels, start=0.0, step=0.1):
    """Levels at 10 per second, as ebur128 prints them. Returns the last answer."""
    moving = None
    for i, level in enumerate(levels):
        moving = follow.update(level, start + i * step)
    return moving


def test_the_words_move_while_you_talk():
    f = VoiceFollow()
    feed(f, [ROOM] * 20)
    assert feed(f, [VOICE] * 5, start=2.0) is True


def test_the_words_hold_still_when_you_stop():
    f = VoiceFollow()
    feed(f, [ROOM] * 20)
    feed(f, [VOICE] * 10, start=2.0)
    assert feed(f, [ROOM] * 15, start=3.0) is False


def test_the_gap_between_two_words_does_not_stop_them():
    f = VoiceFollow()
    feed(f, [ROOM] * 20)
    feed(f, [VOICE] * 10, start=2.0)
    assert feed(f, [ROOM] * 3, start=3.0) is True


def test_before_it_has_heard_the_room_it_scrolls_as_it_always_did():
    """Talking from the first instant means no quiet to learn from yet."""
    f = VoiceFollow()
    assert feed(f, [VOICE] * 5) is True
    assert VoiceFollow().update(ROOM, 0.0) is True


def test_the_meters_first_empty_readings_do_not_blind_it():
    """The retake that never stopped. ebur128 reports M:-120.7 for its
    first 0.3 s -- "nothing measured yet", measured on a real take whose
    room sat at -59 and voice at -33 to -25. Learned as the room, that
    made the room itself sound like talking, for the rest of the take.
    Whether the window caught those readings was timing, so the first
    take worked and the retake did not."""
    f = VoiceFollow()
    feed(f, [-120.7] * 3 + [ROOM] * 17)
    feed(f, [VOICE] * 10, start=2.0)
    assert feed(f, [ROOM] * 15, start=3.0) is False


def test_a_quiet_microphone_is_still_followed():
    """A mic turned down 17 dB moves the voice and the room together."""
    f = VoiceFollow()
    feed(f, [ROOM - 17] * 20)
    assert feed(f, [VOICE - 17] * 5, start=2.0) is True
    assert feed(f, [ROOM - 17] * 15, start=2.5) is False
