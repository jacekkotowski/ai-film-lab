"""Each slide is recorded as its own take, and can be said again at once.

Jacek, 2026-10-02: "It is impossible to record without errors. I want the
recording of slides rebuilt so that each slide is recorded separately,
and 'fluffed it, record again' is available immediately for that slide."

One long take over all the pictures lost everything when anything went
wrong: that morning the Windows audio engine died one second into a
take and the whole take with it. Now the window records one picture per
take; Enter keeps it and moves on, R throws THIS one away and says it
again. When the last slide is kept, the takes are joined into the one
narration the film already knows how to cut, and the cues are written at
the joins -- so nothing after the recording changes.

The window and ffmpeg cannot be tested. Every decision in them is here.
"""

from pytest import approx

from ffilm import booth, kinds, record


def test_the_cuts_fall_where_each_slide_ends():
    assert record.slide_cues([3.0, 4.5, 2.0]) == approx([3.0, 7.5])


def test_one_slide_has_nothing_to_cut():
    assert record.slide_cues([6.0]) == []


def test_the_cuts_match_the_pictures_shown():
    shown = ["media/a.png", "media/b.png", "media/c.png"]
    cues = record.slide_cues([3.0, 4.5, 2.0])
    assert len(cues) + 1 == len(shown)


def test_space_ends_the_slide_not_the_narration_on_every_slide():
    assert booth.next_label(0, 5, per_slide=True) == booth.next_label(
        4, 5, per_slide=True)
    assert "slide" in booth.next_label(0, 5, per_slide=True).lower()


def test_enter_after_the_last_slide_finishes_and_otherwise_moves_on():
    assert booth.after_slide(step=1, n=5) == 2
    assert booth.after_slide(step=4, n=5) is None


def test_slide_takes_are_kept_out_of_the_material_until_they_are_joined():
    # a half-finished sitting must not look like a narration
    assert kinds.SLIDES_DIRNAME in kinds.ASIDE_DIRNAMES
