# The developer's rulebook

You are changing the machine, not a film. This file loads when you touch
anything under `ffilm/`. Being here means I asked for it. If I didn't,
stop and go back to `projects/CLAUDE.md`.

The step-by-step procedure is the `change-the-machine` skill. When the
cause of a fault is not yet known, use the `investigate` skill first.

---

## Standing requests

- **Leave the sound chain alone** (`audio.py`, and the ducking and loudness
  inside it). Settled on 2026-09-12, and I asked for it not to be touched
  again. See `docs/decisions/0003-gate-before-the-expander.md`.
- **Speed ideas that are already measured dead ends** are listed in
  `docs/decisions/0002-where-render-time-goes.md`. Do not re-propose one
  without new measurements.

## Measure before claiming

Reasoning from the code alone has given four confident, wrong answers in
this repo, about render cost, encoder presets, parallel rendering and
background noise. So:

- **Performance:** run `cProfile`, or time the real command, *before*
  naming where the time goes.
- **Sound:** measure with ffmpeg (`volumedetect`, `ebur128`, band-split
  RMS) across the *whole* take. Two well-chosen points are not a trend.
- **In the answer, separate what you measured from what you inferred.**
  When a premise turns out wrong, say so first, before doing the work.

## The rules the tests enforce

`uv run --extra dev pytest` runs in under a second, and it runs after any
change to `ffilm/`. Every test exists because that rule broke in front of
me once. Test names are sentences (`test_nothing_goes_missing.py`); a new
rule gets a new sentence.

Tests cover **pure functions only**: no ffmpeg, no camera, no rendering.
If something can only be tested by rendering, pull the decision out into
a pure function and test that.

## Rules that are not obvious from the code

- **Never call `cv2.imread` or `cv2.imwrite` directly.** Use `pix.py`.
  OpenCV cannot open a non-ASCII path on Windows, and it says so by
  returning `None`.
- **Name everything derived with `ingest.analysis_keys()`**, never the bare
  filename. `IMG_0042` appears in every folder on a camera card.
- **Devices are discovered, never hardcoded** (`record.py`). The choice is
  remembered per *machine* in `.devices.json`.
- **dshow will not give one webcam to two programs.** `booth.py` splits one
  ffmpeg's picture; it never maps it twice. Mapping twice starves the file.
- **`uv.lock` is tracked.** A version range once resolved OpenCV to 5.0,
  which silently removed face detection. See
  `docs/decisions/0001-lock-the-dependencies.md`.
- **Windows first.** Paths contain spaces and Polish letters. Quote them.

## The map

Read the spine first, in this order. Each module's docstring is the
authoritative description; this table is only the index.

```
THE SPINE
  spec.py         what a film IS. Everything else turns these objects into pixels
  scaffold.py     media -> a first film.yaml. All editing decisions live here
  render.py       film.yaml -> pixels. The camera is one function, `warp`
  moves.py        the movement vocabulary + the taste constants

GETTING THE MATERIAL          LOOKING AT THE MATERIAL
  record.py   camera + mic      ingest.py   contact sheet, manifest, proxies, pauses
  booth.py    the record window kinds.py    what counts as a photo / clip / track
                                segment.py  where the person is, for bokeh
                                pix.py      read/write a still, whatever it is called
FOUNDATIONS
  ffmpeg.py   find ffmpeg/ffprobe   fonts.py  typefaces, wrapping   paths.py  where the toolkit is
SOUND AND WORDS
  audio.py        speech + narration + music -> one track
  voice.py        speech -> timed lines (optional extra: voice)
  caption_fit.py  which line belongs on which shot
  cover.py        the thumbnail. Not part of the film
  library.py      the shared shelf: music + two cover backdrops

THE WAY IN
  cli.py      the commands        guide.py    `uv run film`: what next?
  checks.py   what is wrong, found before the render finds it
  editor.py   the browser bench   history.py  render commits film.yaml -> undo
  pack.py     a zip for another computer
```

## The layers

`tests/test_imports_only_point_down.py` sorts every module into a layer
and fails if an import points up. There are no exceptions:

```
9  cli                                  the command line
8  guide, editor                        the ways in
7  scaffold, booth, checks              workflows
6  render, caption_fit                  pixels; captions fitted to shots
5  audio, voice, cover                  sound and words
4  record, ingest, segment              getting and reading the material
3  moves      2  spec      1  library
0  kinds, pix, paths, ffmpeg, fonts, history, pack
```

When a new module needs something from a module at the same or a higher
layer, move the shared piece *down*. That is how `ffmpeg.py`, `fonts.py`,
`paths.py` and `checks.py` came to exist. New logic never goes in `cli.py`:
the checks live in `checks.py`, and cli only prints them.
