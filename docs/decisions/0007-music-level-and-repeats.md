# 0007 — Why is every music track brought to -20 LUFS, and how does it repeat?

**Status:** settled 2026-09-16  ·  **Commits:** 16fa8c8

## The question
Two faults under the music. A track shorter than the film was looped
with `-stream_loop`, and "I am not your fear" had dead air at 3:08. And
each track came in at whatever it was mastered at, under one
`music_volume`.

## What was measured
Tracks on the machine, ebur128 integrated loudness:

| track | LUFS | bed at 0.6, against the voice at -20 |
|---|---:|---:|
| Stellardrone, Red Giant | -13.5 | 2.1 dB above the voice |
| library tibetan_cafe | -44.3 | 28.7 dB below, not heard |

Music bed alone, longest stretch under -50 dBFS away from the two ends
of a 215.9 s film:

| how the ends are trimmed | stretch |
|---|---:|
| `-stream_loop`, nothing trimmed | 17.5 s |
| silence under a fixed -50 dB | 11.0 s |
| 23 dB under the track's loudness | 2.75 s |
| 18 dB under the track's loudness | 1.0 s |

## The decision
- Each track is measured once (cached in `analysis/music.json`) and
  brought to `MUSIC_TARGET_LUFS = -20` before `music_volume`. That is
  the voice's own target, so `music_volume: 1.0` means "as loud as the
  voice" on every film. **Chosen by reasoning, not by ear.** Both beds
  measure -24.0 LUFS at 0.6.
- Its quiet head and tail, 18 dB under its loudness, are cut off; it
  repeats with a 5 s crossfade, at most 12 times. A film that ends
  inside the track's own fade plays into it once.
- `film check` says when the music repeats or stops early.

## Reopen it only if
Jacek says the music is too loud or too quiet on a film where the voice
measures right. Then change `music_volume` on that film first; move the
target only if the same complaint comes from two different tracks.
