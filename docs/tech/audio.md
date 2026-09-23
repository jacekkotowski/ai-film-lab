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

## Measuring
```
ffmpeg -i f -af volumedetect -f null -     # mean/max dB
ffmpeg -i f -af ebur128 -f null -          # loudness
```
Sweep the whole take — two points are not a trend.

## Tools
[[ffmpeg]].
