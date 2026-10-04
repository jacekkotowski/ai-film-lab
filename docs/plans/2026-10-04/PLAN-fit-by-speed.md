# Plan: fit a film that is slightly over by raising `speed:` a little

**Date:** 2026-10-04 (revised the same day). **Status:** BUILT
(`film fit`, `checks.speed_to_fit`, `scaffold.refit_speed`,
`record.MAX_SPEED`; test `test_fitting_by_speed_keeps_every_caption_on_its_word`,
8 tests). Dry-run only on real films so far; not yet applied to one, not
rendered. `MAX_SPEED` 1.25 is still unmeasured. Deviation from the text
below: the rewrite is in `scaffold.py` as planned, the solver in
`checks.py` as planned; a flow-style caption makes it refuse (ValueError).
The first version of this plan was wrong (see "What the first version got
wrong").

## The goal

A film is a few seconds over a limit (a Short is 180 s; later films may
have other limits). Instead of cutting a sentence, raise the speed of
everything spoken by a few percent, for example 1.2 -> 1.24, to land just
under the limit. The limit is a parameter, `--target N`, and 180 is only
one value of it.

## What the first version got wrong

It said "no code is needed, just change the digit." That was reasoned
from half the code. Reading `caption_fit.py:40-64` and `spec.py:101-109`:

- Caption `at:`, `dur:` and `words:` are stored in **film seconds**,
  already divided by the shot's speed when `film caption` wrote them.
- Changing `speed:` moves the words and the picture together, but **not
  the captions.** At 1.2 -> 1.24, a caption 28 s into a shot ends up
  about 0.9 s late (28 x (1 - 1.2/1.24)). That number was calculated, not
  measured on a render.
- `spec.py:612` trims a caption that runs past its shot **without a
  warning**, so `film check` would not catch it.
- Re-running `film caption` would fix the timing but re-transcribe
  (slow), and it throws away captions placed by `fix-captions`.

## The correct transform

Film time = (source time - `in`) / speed. Changing speed from a to b
multiplies every film time inside that shot by a/b. So for every shot
whose speed changes:

- `speed:` a -> b
- each caption: `at`, `dur` and every value in `words` times a/b

This transform is exact, not an approximation, and needs no
transcription. It is also tedious and error-prone by hand: a 10-shot film
has dozens of numbers. So it belongs in code, not in a skill's arithmetic.

## What to build (one command, about 60 lines plus one test)

`uv run film fit -p NAME --target 175`

1. **Pure function** in `checks.py` (layer 7, no new module):
   `speed_to_fit(film, target) -> float | None`. It solves
   `total(s) = target` using the same per-shot rules as `spec.Shot.parse`
   (clips and slides divide by speed; `duration:`, `VOICE_TAIL` and silent
   pictures are fixed), rounds s **up** to 2 decimals, and returns None if
   s would exceed `MAX_SPEED`.
2. **Pure text rewrite** in `scaffold.py`, following the existing
   `add_captions` / `recut_slides` pattern: edit the numbers in place,
   keep every comment and note, and no YAML round-trip.
3. **CLI:** `keep_a_copy`, write, `Film.load` to validate, restore on
   failure (the pattern at `cli.py:510-514`). Print before and after: the
   speed, the total and the seconds saved.
4. **`--dry-run`** prints the speed it would use and writes nothing. This
   is what `fit-to-length` calls first.
5. **Test, named as a sentence:**
   `test_fitting_by_speed_keeps_every_caption_on_its_word.py`. For a
   small film, after `fit`: (a) `film.duration <= target`; (b) every
   caption's source-time position, `at x speed + in`, is unchanged to
   0.01 s; (c) comments survive.

Scope rules:
- **Which shots:** every shot with `speed != 1.0` that carries speech
  (`rec_*` and `voice:` slides), all set to the same s. Decision 0010:
  one voice, one speed. A clip with no voice is left alone.
- **One constant, `MAX_SPEED`**, next to `REC_SPEED` in `record.py`.
  Above it, `fit` refuses and names the seconds still over: that is a
  cutting job for `fit-to-length`.
- **No `draft at 1.0`.** Draft and final read the same `film.yaml`, so
  the draft shows the length that ships and caption timing stays the
  same in both.
- **Not touched:** `audio.py` (standing request). It already takes speed
  per shot, and the voiced-take cache is keyed by speed
  (`audio.voiced_name`), so a new speed makes one new voiced file per
  take. That costs time once at the first draft; how much is not measured.

## To measure before trusting it

- **`MAX_SPEED`.** Start at 1.25 as a placeholder. Measure on one real
  take at 1.20 / 1.25 / 1.30: words per minute, and atempo artefacts by
  numbers (spectral flatness or `astats` on the speech band). Do not ask
  Jacek to pick by ear.
- **The first real use:** `film check` total vs target, one `film draft`,
  and one caption near the end of the longest spoken shot checked
  against its word.

## Order inside `fit-to-length` once built

1. `film go --target` (shortens silent photographs, no voice change)
2. `film fit --dry-run`: if it gives a speed at or under `MAX_SPEED`,
   propose it and wait for go
3. otherwise cut repetition (the existing steps)

## Not doing

- A different speed per block (intro/outro vs narration). It makes an
  audible step (0010).
- Time-stretching music or pauses. Silence is already fixed (`VOICE_TAIL`).
- Any new dependency.
