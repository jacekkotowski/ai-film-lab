# Audio — levels, noise, music, speed

**The sound chain (`audio.py`) is settled; change it only when Jacek asks.**
He judges sound by numbers, not by ear — always give dB/LUFS.

## Settled (read the decision before touching)
| Topic | Decision |
|---|---|
| Room noise late in a take: gate before the expander | 0003 |
| Music at −20 LUFS, trimmed 18 dB under, 5 s crossfade on repeat | 0007 |
| RNNoise after both gates; before speechnorm ffmpeg hangs | 0008 |
| Everything he speaks plays at 1.2 (camera and narration) | 0010 |

## Order of the speech chain (`audio.speech_chain`)
trim (source clock) → asetpts → aresample 44100 → atempo (speed) → lift →
fades (post-tempo length) → delay. Camera takes are read `sound_lag`
seconds later first — see [[sync]].

## Pauses and speed, measured 2026-10-05 (SUMIFS SUMPRODUCT vs DAX, 202.96 s)
Detector: `ingest.quiet_stretches` (50 ms RMS, line −41 dB), min gap
0.25 s, inside each shot's in/out, edge pauses left out. Seconds as played (÷1.2).

| band | camera (35.5 s) | narration (163.0 s) |
|---|---|---|
| 0.25–0.4 s | 4 / 1.1 s | 11 / 2.7 s |
| 0.4–0.6 s | 2 / 0.8 s | 9 / 3.5 s |
| 0.6–1.0 s | 6 / 4.0 s | 18 / 12.2 s |
| 1.0–1.5 s | 0 | 11 / 10.7 s |
| > 1.5 s | 0 | 1 / 2.5 s (s07, 3.0 s source) |

Longest camera pause 0.90 s, so `PAUSE_DROP = 1.5` cuts nothing here.
Every pause ≥ 0.6 s cut to 0.4 s saves 2.0 s (camera) + 15.5 s (narration).
Rate: 89 wpm as recorded, 107 at 1.2, 112 at 1.25, 125 at 1.4, 134 at 1.5
(caption words; a number counts as one word).
atempo s then 1/s, log-spectral distance on voiced frames, median:
1.05 4.9 dB · 1.10 5.2 · 1.15–1.30 6.5–6.7 · 1.40 7.2 · 1.50 7.4 · 1.60 8.1.
A proxy for artefacts, not a listening test; no sharp knee in 1.15–1.5.
Checked against faster-whisper small word times (308 words): every
narration word gap ≥ 0.6 s is a detected pause (0 missed). 24 of 30
pauses ≥ 0.6 s have a whisper word overlapping them, mostly 0.1–0.5 s at
an edge, yet the level inside every pause is median −56.6 to −45.7 dB
(line −41.1): whisper stretches words over silence (",157" spans 4.1 s).
Whisper gaps sum 25.0 s vs 30.5 s by level. The 3.0 s s07 pause is
lead-in before the first word ("Data", 196.11 s), not mid-speech.

## Measuring
```
ffmpeg -i f -af volumedetect -f null -     # mean/max dB
ffmpeg -i f -af ebur128 -f null -          # loudness
```
Sweep the whole take — two points are not a trend.

## Tools
[[ffmpeg]].
