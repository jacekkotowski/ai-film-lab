---
name: fix-captions
description: Fix captions that flash and vanish, start late, or never show — usually words the English transcriber did not hear (German, Polish, names, numbers). Places each caption on the speech measured in the audio, keeps the script's spelling, never invents word timings. Use when the user says "the caption disappeared", "the German words don't show", "the caption is gone before I finish the sentence".
---

# Fix captions: put the words where they were actually said

`film caption --apply` places every line by listening. The text comes
from the script, so the *spelling* is always right. The *timing* comes
from the transcriber, and where it did not hear a word it has nothing to
time. A four-word German title with one word heard is squeezed onto that
one word: on screen for under a second, and late. The machine cannot
tell a misheard title from a fast speaker. That is the judgement here.

Done first on 2026-09-19, German Forgotten Bauhaus Hope. Four captions
were on screen for 0.42–1.14 s. On the speech measured in the audio they
came out at 1.50–5.30 s:

| caption | before | after |
|---|---|---|
| "Hannes Meyer's Laubenganghäuser, 1930" | 0.78 s | 5.30 s |
| "Haus am Horn, interior" | 0.42 s | 3.85 s |
| "Laubenganghaus kitchen/interior" | 1.14 s | 2.95 s |
| "Bauhaus." | 0.46 s | 1.50 s |

## Steps

1. **Re-read `film.yaml`** (the edit-pass rule: the bench may have
   changed it).

2. **Find the suspects, by rule.** A caption is suspect if either:
   - it is on screen for **under 1.2 s**; or
   - its `words:` holds **fewer than half** as many times as the text
     has words.

   On the Bauhaus film this caught all four above, and two short lines
   worth a look ("Light,", "space, and air,"). A plain seconds-per-word
   rule missed two and flagged a correct fast line, so don't use one.
   The user's note ("the caption on picture 3") wins over the rule.

3. **Find where it was really said.**
   - Look it up in `analysis/transcript.txt`: the heard times of the
     suspect line, and of the lines on either side of it.
   - Measure the pauses in that stretch of the source:
     `ffmpeg -ss A -t D -i SOURCE -af silencedetect=noise=-38dB:d=0.35 -f null -`.
     The source is the narration `.wav` for a picture, the take for a
     clip.
   - The caption belongs to **the speech between the pause after the
     previous line and the pause before the next one**.
   - Example: the transcriber put "Hannes Meyer's…" at 49.21–49.99 s.
     Measured, the speech ran 45.35–50.66 s.

4. **Convert to the shot's clock.** `at:` is in seconds from the start of
   the shot, as played:
   - a picture: source seconds − `in:`;
   - a clip: (source seconds − `in:`) ÷ `speed:`.

   Set `at:` to the start of the speech. Set `dur:` so the caption ends at
   the pause, and never runs into the next caption's `at:`.

5. **`words:`: re-express, never invent.** Keep the transcriber's
   measured times, moved to the new `at:`:
   new offset = old `at:` + old offset − new `at:`.

   With one heard word, the highlight arrives late on that caption. Say
   so; don't fill in times.

6. **Add a `#` comment** above each caption you fixed: "German not heard
   by the transcriber: placed on the speech measured in the audio
   (A–B s)". `note:` belongs to shots, not to captions.

7. **`film check`**, then `film peek`. To confirm with a frame, grab one
   at shot start + `at:` + 60% of `dur:` from the render and look at it.

## Never

- Retype the caption text "to be safe". It is the script's, and it is
  already right.
- Spread `words:` evenly, or type any time that was not measured
  (`projects/CLAUDE.md`).
- Stretch a caption across a pause into the next sentence to make it
  longer. If a one-word line ("Light,") is still short, leave it and say
  so.
