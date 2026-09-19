"""
A take said to the camera before the narration opens the film; one said
after it closes the film. The pictures sit between them.

Found 2026-09-19: an intro recorded first, photos numbered 1_ to 10_,
and the numbers put every photo ahead of the intro -- the film would
have opened on the slides and ended on "hello".
"""

from ffilm.scaffold import _hint, place_takes


def tagged(*paths):
    out = []
    for p in paths:
        role, num, clean = _hint(p.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        out.append({"entry": {"path": p}, "role": role, "num": num,
                    "clean": clean})
    return out


def paths(ts):
    return [t["entry"]["path"] for t in ts]


def test_a_take_before_the_narration_opens_and_one_after_it_closes():
    order = tagged("media/1_.jpg", "media/2_.jpg",
                   "media/rec_20260919-122456.mp4",
                   "media/rec_20260919-140000.mp4")
    got = place_takes(order, "voiceover_20260919-130000.wav")
    assert paths(got) == ["media/rec_20260919-122456.mp4",
                          "media/1_.jpg", "media/2_.jpg",
                          "media/rec_20260919-140000.mp4"]


def test_with_no_narration_nothing_moves():
    order = tagged("media/1_.jpg", "media/rec_20260919-122456.mp4")
    assert place_takes(order, None) == order


def test_a_closing_word_comes_before_the_card_that_closes_the_film():
    order = tagged("media/open_close_hello.png", "media/1_.jpg",
                   "media/rec_20260919-140000.mp4")
    order.append(order[0])                   # open_close plays again last
    got = place_takes(order, "voiceover_20260919-130000.wav")
    assert paths(got) == ["media/open_close_hello.png", "media/1_.jpg",
                          "media/rec_20260919-140000.mp4",
                          "media/open_close_hello.png"]


def test_a_clip_you_numbered_stays_where_you_numbered_it():
    order = tagged("media/1_.jpg", "media/2_rec_20260919-122456.mp4")
    assert place_takes(order, "voiceover_20260919-130000.wav") == order
