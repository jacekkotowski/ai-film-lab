# 0003 — Why was there room noise late in a take, and what fixed it?

**Status:** settled 2026-09-12; the sound chain is not to be touched again
without an explicit request  ·  **Commits:** a40e16f, 5e4c58d

## The question
Reported 2026-09-11: background noise under the voice, absent in the
opening shots and arriving towards the end of the film.

## Two wrong first guesses, recorded so they are not re-run
- *"The room gets louder across the take."* It does not. Median level in
  all 60 pauses: first half −51.3 dB, second half −51.3 dB, and the noisiest
  stretch is in the **middle**.
- *"The speaker gets quieter towards the end."* Not in the windows that
  matter.

Both came from two well-chosen measurements. A sweep of every pause
contradicted both.

## The cause
The noise gate's threshold was computed from the *source* statistics, but
the gate sat *after* `speechnorm`, which lifts the room by a variable
3–4.5 dB. So the threshold landed inside the room's own scatter, and the
gate closed on about half the pauses: it took 14.3 dB off the room at 22 s
and only 3.0 dB at 247 s of the same take.

## The fix
A second gate **before** the expander. There the level is exactly known:
after the flat gain the voice is at `LEVEL_TARGET_LUFS` and the room at
`room_db + gain`, and nothing has moved them relative to each other yet.
Same `GATE_FRACTION`, applied on the scale the signal is really on.

## What was measured after
Whole film, **music off**, per 15-second block:

| measure                 | before   | after    |
|-------------------------|---------:|---------:|
| worst block             | −43.1 dB | −82.0 dB |
| the ending              | −45.6 dB | −88.8 dB |
| spread across blocks    |  28.4 dB |  12.7 dB |
| voice, largest change   |    —     |  0.03 dB |

Integrated loudness is unchanged. The user listened and accepted the result.

## The trick worth keeping
Render with `film.music = None` and look at the 10th percentile per
15-second block. **Music masks the room** in exactly the quiet stretches
where the complaint is.

## Reopen it only if
The user asks. A little brown-noise room tone under the voice remains, and
it was accepted as it is.
