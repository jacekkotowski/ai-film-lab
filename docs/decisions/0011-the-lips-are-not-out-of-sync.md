# 0011 — Were the lips out of sync in the closing? No. Measured.

**Date:** 2026-09-21
**Status:** settled — the render puts picture and sound together within
about 40 ms. Carried as "FIRST" in the 2026-09-20 plan and again in the
2026-09-21 plan; do not carry it a third time without new evidence.

## The question

Jacek, on the Bauhaus Short's final: "the second spoken part is out of
sync... I am still moving lips, it stays behind the soundtrack which is
faster. This 1.22 speed, is it not a problem?"

"The second spoken part" is s15–s17, the closing. **At the time of the
complaint those shots were at `speed: 1.0`, not 1.22** — the 1.2→1.0
change had been made the evening before. The intro (s01, s03) was at 1.2.

## What was measured

On `out/final.mp4` as rendered on 2026-09-19 at 18:12 — the file he
watched. Audio compared by cross-correlating the log-RMS envelope (10 ms
bins) of the final against the source take, `atempo`-matched to the
shot's speed.

**Audio placement, in 4-second windows across each shot:**

| window of shot | s01 (speed 1.2) | s15 (speed 1.0) |
|---|---:|---:|
| 0–4 s   | −40 ms (r=0.96) | +60 ms (r=0.75) |
| ~4–8 s  | −30 ms (r=0.97) | +50 ms (r=0.85) |
| ~8–12 s | −30 ms (r=0.97) | +60 ms (r=0.82) |
| ~13–17 s| −30 ms (r=0.98) | +50 ms (r=0.85) |
| ~17–21 s| −30 ms (r=0.95) | +50 ms (r=0.84) |

**Picture placement** — every hard cut in the film, by ffmpeg scene
detection, against the shot starts `film check` reports (themselves
rounded to 0.1 s, so ±50 ms is this method's own floor):

| expected | detected | error |
|---:|---:|---:|
| 2.00 | 2.00 | +0 ms |
| 34.20 | 34.25 | +50 ms |
| 52.30 | 52.29 | −8 ms |
| 70.40 | 70.33 | −67 ms |
| 95.00 | 94.92 | −83 ms |
| 110.00 | 109.92 | −83 ms |
| **139.00 (s15)** | **138.92** | **−83 ms** |

## The answer

*Measured:* the audio offset is **constant** across each shot — it does
not grow — at both 1.2 and 1.0. *Measured:* the picture cuts land where
they are supposed to, through the whole film. Picture and sound are
together to within about **40 ms**, and the plan's own threshold for a
visible error is 80 ms.

**There is no lip-sync fault in the render.** The 1.22 speed is not the
cause, and could not have been: the shot complained about was at 1.0.

### Two hypotheses from the 2026-09-20 plan, both rejected on numbers

- *"A piece is cut at the wrong place when the speed changes within a
  take."* No. The final's audio correlates with the source at the
  expected position at r up to 0.98.
- *"At 1.2 the audio `atempo` and the picture step drift apart over a
  long shot."* No. Over s01's 21 measured seconds the offset moves by
  10 ms, which is one envelope bin.

### What is left, and it is not sync

*Inferred, not measured:* the closing ran at 1.0 while everything before
it ran at 1.2. That is a change of **pace** at a cut, not a loss of sync,
and it is the kind of thing that reads as "wrong" without being
mistimed. Decision 0010 had already settled that everything Jacek speaks
plays at 1.2; the Bauhaus closing was the last place still at 1.0, and it
was put to 1.2 on 2026-09-21 at his instruction. Its captions were
divided by 1.2, which is exact: they had been ×1.2 of the source spans,
verified line by line against `analysis/transcript.txt`.

*Also ruled out, measured:* the captions were not lagging. At speed 1.0
each caption's `at:`/`dur:` equalled the transcriber's source span minus
`in:` exactly, on every line of s15 and s16.

## What did not work, so nobody repeats it

Four attempts to measure the **picture** side by lip motion all returned
correlations at noise level and must not be trusted or re-run as-is:

| method | result |
|---|---|
| whole-frame difference, final vs source | r = 0.12 / 0.16 |
| mouth-box difference, per-shot crops | r = 0.11 / 0.15 |
| mouth-vs-own-voice within each file | r = 0.12–0.22 |
| raw frame matching against the source | r ≈ 0.6 but **flat** — runner-up equal to 3 decimals |
| mouth motion-image matching, matched sampling | r = 0.013–0.017 |

A talking head at 24 fps, graded and re-cropped, does not give a mouth
signal strong enough to correlate against its 60 fps source. Scene-cut
detection answered the same question in one command.

## Reopen it only if

Jacek sees it again in a render made after 2026-09-21. Then get the
**shot id and the time on the clock** from him first: two days were spent
on this one without ever establishing that the shot in question was at
1.0 rather than 1.22.
