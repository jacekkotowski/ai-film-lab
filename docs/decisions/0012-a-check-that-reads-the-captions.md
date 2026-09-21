# 0012 — What does `film check` say about the captions, and why those numbers?

**Date:** 2026-09-21
**Status:** settled · **Commits:** `348940b`, `27945a7`

## The question

*Why there are wars* was **published** with two caption faults in it, and
`film check` had printed `OK` on both. Neither was a rendering bug; in
both cases the toolkit produced something obviously impossible and said
nothing about it.

1. The intro's four captions were on screen for 0.26–0.58 s. The
   transcriber had returned the right **words** and junk **times**, and
   `film caption` placed them on the spans it was handed.
2. `s06` said and showed its line at 1:40 and again at 1:44.

The rules for both already existed in prose — the `fix-captions` skill
carries the first, `fit-to-length` the second — and neither had ever been
code. Jacek asked for the repair on 2026-09-21.

## What was added

Two pure functions in `checks.py`, printed by `cmd_check`:

- `unreadable_captions(film)` — a caption that cannot be read in the time
  it is given, or whose `words:` cannot place the highlight.
- `repeated_captions(film)` — lines the film says more than once, and
  where each one is on the film's clock.

## The numbers, and how they were arrived at

**`CAPTION_MIN_READ = 1.2` s** — from the `fix-captions` skill, which
derived it on Bauhaus.

**`CAPTION_MIN_PER_WORD = 0.15` s** — measured here, not chosen. The
first attempt used 0.30 s/word, swept all 19 films in `projects/`, and
returned **41 captions, most of them correct**:

| flagged at 0.30 | s/word | verdict |
|---|---:|---|
| "That is the tradition." 1.04 s | 0.26 | fine — 3.8 words/sec |
| "Mother and child." 0.78 s | 0.26 | fine |
| "Stamped." 0.28 s | 0.28 | fine — one word |
| "It is a risk." 0.45 s | 0.11 | **really is impossible** |

Two things that sweep taught, both invisible from the code:

- **`stop_overlap` shortens captions on purpose**, so they do not collide
  with the next one. A short `dur` is therefore very often *correct*, and
  duration alone is a weak signal.
- Jacek speaks at 97–110 wpm, about **0.45–0.51 s/word played**. 0.15
  s/word is 400 wpm.

The captions that shipped invisible were at **0.026–0.097 s/word**. The
shortest *correct* line anywhere in the repo is **0.24**. Nothing sits
between, so the threshold is not finely balanced. At 0.15 the sweep
returns **12 captions in 6 films, every one real**.

**`REPEAT_MIN_WORDS = 3`** — measured the same way: at 3 the sweep
returns 9 lines in 7 films. Four would drop `"I chose particular."`,
which appears twice in the same shot in *two different films* and has
the shape of exactly this bug.

## Two faults, worded apart

A caption placed by hand on the measured speech is on screen for five
seconds and perfectly readable; what is still wrong is that its
highlight has one word time to follow. Bauhaus's two German titles are
that — fixed and **accepted** on 2026-09-19. Calling them unreadable
would send Jacek back to something already settled, so they read *"a
caption whose highlight cannot follow the words"* instead.

## What this cannot do, said plainly

`repeated_captions` **cannot tell a repeated take from a refrain
somebody meant.** `I am not your fear` is a poem and trips it four
times. The note says where both are and decides nothing. If that becomes
noise, the fix is not a cleverer rule — it is a way for a film to say
"this repeat is deliberate".

## Reopen it only if

A real fault gets through at these numbers, or the sweep starts returning
lines that are fine. **Re-run the sweep before changing either constant**
— it is the only thing that makes them defensible, and both were wrong on
the first guess.
