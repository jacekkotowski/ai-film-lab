# 0008 — Which speech denoiser, where in the chain, and how does it get onto a new computer?

**Status:** settled 2026-09-16  ·  **Code:** `ffilm/models.py`, `audio.SPEECH_DENOISE`

## The question
After 0003 the pauses were clean (-78 to -82 dBFS), and background noise
was still audible: the room under and between the words, 36 dB below the
voice, where a gate never closes. More `afftdn` and adding `anlmdn`
changed it by 0.1 and 0.3 dB. The one lever left without a fifth package
was RNNoise, a model file that ffmpeg's `arnndn` reads. Jacek gave the OK
to download it and asked that installing it be automatic and kept in the
visible `models/` folder.

## What was measured
The rule was written before any result: the room under the words down by
8 dB or more, and the consonant bands (3-6 kHz, 6-10 kHz) moved by 1 dB
or less. Two models from GregorR/rnnoise-models: `sh` (recording noise,
speech) and `bd` (recording noise, voice). 34 s stretches of "I am not
your fear":

| model, position | stretch | room | 3-6 kHz | 6-10 kHz | |
|---|---|---:|---:|---:|---|
| sh, after both gates | 20-54 s | -13.8 | -0.1 | +0.1 | go |
| sh, after both gates | 150-184 s | -16.0 | +0.5 | +0.6 | go |
| bd, after both gates | 20-54 s | -14.9 | -1.8 | -1.1 | no-go |
| bd, after speechnorm | 20-54 s | ffmpeg failed | | | |

Whole take, sh after both gates, 15 s blocks: median -14.7 dB, every block
at least -10 dB except the silent tail (-7.5); whole-take bands -0.5 and
-0.7 dB.

**The hang.** With `arnndn` anywhere before `speechnorm`, ffmpeg 9.0.1
wrote 96% of the file and then never exited: 3 of 3 runs, with stdin
closed, at 44.1 and 48 kHz, with fixed 1024-sample frames. After
`speechnorm`: 1.2 s, and five whole takes from three films finished in
5-11 s.

## The decision
- `sh.rnnn`, after both gates, before the voice character. A test fails
  if it is ever moved before `speechnorm`. `VOICE_VERSION` 6.
- The model is an entry in `models.CATALOGUE` with its URL, size and
  SHA-256. It is fetched the first time it is needed, checked, and saved
  in `models/`; a wrong or partial download is refused and leaves nothing
  behind. `film models` fetches everything up front, `film doctor` lists
  it, and `film pack` carries `models/README.md` but not the files. The
  bokeh model moved into the same catalogue.
- ffmpeg runs from `models/` so the filter names the file without a
  Windows path, whose drive-letter colon a filter option would need
  escaped.
- No network: the take is voiced without it, a line says so, and the
  cached file's name records which chain made it.
- Render cost: draft of the 178.7 s film 87 s before, 101 s with the
  models fetched in the same run.

## Reopen it only if
A render hangs in the voice step, or a take where consonants measure
more than 1 dB lower with it than without.
