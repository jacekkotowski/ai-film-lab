# 0010 — Your narration is you talking, so it gets the same speed

**Date:** 2026-09-20
**Status:** settled, after being asked for three times

## What was decided

A slide's `voice:` — the narration read over a photograph — now carries
`REC_SPEED` (1.2) exactly as a `rec_*` talking take does, and `speed:` on
a slide is a live key that shortens the picture and speeds the words
together.

This overturns the comment in `kinds.py`:

> a voiceover is narration read over pictures, not a talking-head clip,
> and REC_SPEED (scaffold's 1.2x for `rec_*`) has no business touching
> somebody's spoken narration.

and the one in `spec.py`:

> Never sped up: `speed` is a correction for talking to a lens, and there
> is no lens here.

## Why

One film, one voice. Measured on 1930s Austria Had Photoshop:

| block | recorded | played at the old defaults |
|---|---|---|
| intro (to camera) | 102 wpm | 122 wpm (×1.2) |
| narration (pictures) | 110 wpm | 110 wpm (×1.0) |
| closing (to camera) | 97 wpm | 116 wpm (×1.2) |

The step between the talking head and the photographs is audible, and it
is the first thing Jacek said about the film. The old rule was defensible
in the abstract — a read narration is not a nervous person talking to a
lens — and wrong in the room.

## The trap this closes

`speed:` on a slide was not ignored. It was **dead**, in a way nothing
reported:

- `spec.py` left the picture on screen for `(out - in) + a breath`,
  whatever `speed:` said;
- `audio.speech_specs` passed a hard `1.0` for every slide;
- `scaffold` never wrote the key at all.

So writing `speed: 1.2` over a photograph changed nothing whatever, and
said nothing about changing nothing. Jacek wrote it and reported no
difference, which is exactly right.

Worse, on 2026-09-20 Claude read *one* of those two halves, inferred the
other, and told him 1.2 on a slide would drift the sound 4.6 s away from
the picture. That was wrong — the audio half never receives the number,
so there is no drift and never was. It is the fifth confident wrong
answer this repo has had from reasoning about code instead of running it
(`ffilm/CLAUDE.md`, "Measure before claiming"), and it cost the producer
three rounds of arguing for something he should have got the first time.

## What holds it

`tests/test_speed_on_a_picture_moves_words_and_picture_together.py`.

The invariant is not "slides are at 1.2" — it is that the **picture and
its words come out the same length at every speed**. The narration is one
continuous recording cut into pieces, so a piece that plays short pushes
every later piece out of step with its photograph. The test asserts that
equality across 1.0, 1.08, 1.2 and 1.5, which is the thing that would
actually break if someone changed one half again.

Two older tests compared a slide's screen time against `(out - in)` in
**source** seconds. They now divide by speed. The rule they check — no
word is cut off — is unchanged.

## What is still true

`duration:` on a slide holds the photograph longer without stretching the
words. That was the rule `audio.py`'s comment was really defending, and
it is untouched and still tested.

## If you want it back

One film: change the digit in `film.yaml`. Every film: `_speed_for` in
`scaffold.py` is the one place, and `REC_SPEED` is the one number.
