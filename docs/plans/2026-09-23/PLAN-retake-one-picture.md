# Re-record one picture's words, not the whole narration

**Status: plan only. Nothing built. Waiting for Jacek.**

## Why

Turn Heat Into Images, one morning (2026-09-23): 10 narration takes and
10 camera takes in `media/_discarded/`. A fluffed sentence over picture 4
meant reading all six pictures again, about 3 minutes each time.

## What already exists (read from the code, not run)

- Every picture shot in `film.yaml` names its own sound file and the
  stretch inside it: `voice: media/voiceover_….wav`, `in:`, `out:`. The
  renderer plays whatever file a shot names. **Rendering needs no change.**
- The narration window (`record --voice`) shows the pictures in
  `scaffold.pictures_in_order` order, each with its own paragraph of
  `narration.txt`.
- `film go --rewrite` rebuilds every picture shot from the newest
  `voiceover_` take and its cues.

## What would be built

1. **`film record --voice --picture 4`**: the same window, showing only
   picture 4 and its paragraph. SPACE ends the take. It saves
   `media/picture4_YYYYMMDD-HHMMSS.wav`. The name deliberately does
   **not** start with `voiceover_`, so it is never taken for the whole
   narration, and the old narration is not put aside (today's rule,
   3855bb7).
2. **That shot is repointed** in `film.yaml`: `voice:` becomes the new
   file, `in: 0`, `out:` its length. Its captions are transcribed again
   from the new take and `narration.txt`'s paragraph. Other shots are
   untouched. Pure function + test: "a retaken picture changes only its
   own shot".
3. **`go --rewrite` keeps a picture retake** that is newer than the
   narration, instead of cutting that picture from the old take again.
   Test: "a rewrite keeps a retaken picture".
4. **The guide offers it**: "...or say the words over one picture again".
   You type its number.

## Risks to check before building

- **Is a `picture4_….wav` in `media/` taken for music?** Check
  `kinds` / `library` for how music is found. Measure, don't assume.
- **The seam.** Picture 4's sound will come from a different take than
  3 and 5: a new level, a new room tone. `audio.py` is off limits
  (standing request), so the question is only whether you notice. Your
  hearing rule applies: measure the level (`ebur128`) of both takes and
  report the difference in dB. Don't ask you to listen for it.
- **The window** can only be tested by using it: walk it, including
  closing it halfway through and reopening it.

## Cost

About 4 pieces, each with a test. Items 1 and 3 touch `cli.py`,
`booth.py` and `scaffold.py`. No new dependency.
