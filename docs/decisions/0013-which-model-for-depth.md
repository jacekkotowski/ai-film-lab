# 0013 — Which model gives a photograph depth, and what runs it?

**Status:** settled 2026-09-28 (runner and file); strength judged on stills
only, not yet on a film Jacek watched  ·  **Plan:** docs/plans/2026-09-27/PLAN-2.5d-parallax.md

## The question
v0.2 gives photographs parallax (`depth:` in film.yaml): as the camera
moves, what is near slides past what is far. It needs a depth map per
photo. Which model, which file, and can OpenCV run it the way it runs the
bokeh model (0006), with no new package?

## Which model
Depth Anything V2 **Small**. Apache-2.0. Base and Large are CC-BY-NC:
not for a toolkit anyone may use.

## What was measured (this PC, CPU, 2026-09-28)

**cv2.dnn cannot run it.** OpenCV 4.14.0, `cv2.dnn.readNetFromONNX`:

| file | source | cv2.dnn |
|---|---|---|
| `model.onnx` fp32, 99 MB | onnx-community | refused: `dynamic 'zero' shapes are not supported` |
| `model_fp16.onnx`, 50 MB | onnx-community | refused: same |
| `model_quantized.onnx` int8, 27 MB | onnx-community | refused: a Reshape node |
| `depth_anything_v2_vits.onnx`, fixed 518x518, 99 MB | fabio-sim v2.0.0 | refused: cannot build its custom layers |

So it runs in **onnxruntime**, as the optional extra `depth`
(`uv sync --extra depth`). Not a new package in practice: onnxruntime
1.29.0 was already in `uv.lock`, pulled in by faster-whisper (`voice`).
Without it photographs render flat and the render says so once.

**onnxruntime, 1 run after 1 warm-up, short side 518:**

| picture | model input | fp32 | fp16 | int8 | fp16 vs fp32 | int8 vs fp32 |
|---|---|---:|---:|---:|---:|---:|
| Bauhaus `1_.jpg` 5317x3440 | 798x518 | 1828 ms | 9124 ms | 1914 ms | 0.0014 | 0.0354 |
| Frankfurt `5_tanks.jfif` 1920x1433 | 700x518 | 1386 ms | 6955 ms | 1465 ms | 0.0008 | 0.0055 |
| Turn Heat `5.jpg` 450x600 | 518x686 | 1341 ms | 7272 ms | 1658 ms | 0.0006 | 0.0111 |
| chart `1german_exports_english.png` | 854x518 | 1841 ms | 9966 ms | 1953 ms | 0.0007 | 0.0708 |
| screenshot `2_git.png` 1920x1080 | 924x518 | 2227 ms | 11573 ms | 2227 ms | 0.0023 | 0.0781 |

Differences are mean absolute difference of the depth maps, each stretched
to 0..1. **fp32 chosen:** fp16 is 5x slower on this CPU and int8 is no faster
and 0.07 off on the chart and the screenshot. The map is made once per
photo and kept in `analysis/depth/`, so 1.3–2.2 s a photo is paid once.

## Strength: edges, judged on stills (pan_right, both ends of the move)
Shift of a pixel against the flat camera, in pixels of a 960-wide frame:

| picture | 0.3 median / p99 | 0.5 median / p99 | 0.8 median / p99 |
|---|---:|---:|---:|
| Bauhaus `1_.jpg` | 3.5 / 8.8 | 5.8 / 14.7 | 9.3 / 23.5 |
| `5_tanks.jfif` | 5.2 / 11.6 | 8.6 / 19.3 | 13.8 / 30.8 |
| Turn Heat `5.jpg` | 0.2 / 15.9 | 0.4 / 26.6 | 0.7 / 42.5 |
| chart | 3.3 / 12.3 | 5.4 / 20.5 | 8.7 / 32.9 |
| screenshot | 3.2 / 11.7 | 5.3 / 19.6 | 8.5 / 31.3 |

Looked at (Claude, on the stills, at full size on the tanks):
- **0.5 is clean.** The gunner slides past the people behind him, no tear.
- **0.8 stretches.** The standing man beside the tank is visibly widened.
- **A chart is not flat to the model.** Its dashed "2022" line bends at 0.5
  and plainly at 0.8; slightly at 0.3. A chart or a screenshot wants
  `depth: 0` on its own shot — the film.yaml header says so.

## Render time
`render()` at FINAL quality (1080x1920, shutter 4), no sound, 4 Bauhaus
photos (s04 s05 s06 s08, 75.7 s of film, 1816 frames), cProfile, one run each,
depth maps already cached:

| | wall | top costs (tottime) |
|---|---:|---|
| flat (`depth: 0`) | 234.1 s | cvtColor 40.0 s, warpAffine 37.8 s, apply_look 32.3 s |
| `depth: 0.5` | 433.1 s (**+85 %**) | source_maps 107.8 s, parallax_maps 82.5 s, remap 38.6 s |

warpAffine's 37.8 s is gone and 229 s of map-building and remapping takes
its place. `source_maps` alone costs 59 ms a frame: numpy arithmetic on
two 1080x1920 grids, promoted to float64 by the matrix entries.
Drafts were not timed.

**Tried 2026-09-28.** `source_maps` multiplied the cached float32 pixel
grids by `inv[0,0]` etc., float64 scalars straight out of
`cv2.invertAffineTransform`; NumPy promotes the whole grid to float64 for
that multiply, then narrows it back at the end. Casting the six `inv[...]`
entries to `np.float32` first keeps the arithmetic in float32 throughout.
Isolated benchmark (a 1968x1523 photo, 1080x1920 output, 300 calls with a
moving window, no ffmpeg, no film): **98.9 ms/call before, ~41 ms/call
after — about 2.4x.** Not yet re-profiled inside a real `film final`, so
the effect on the 433.1 s / +85% figure above is not measured. Guarded by
`tests/test_source_maps_stays_float32.py`: same numbers, still float32.

`parallax_maps` (82.5 s) and `remap` (38.6 s) were not touched — worth
the same look if more speed is wanted, not done yet.

## What was decided, and why
- fp32 Small from onnx-community, run by onnxruntime as an optional extra.
- Off by default (`depth: 0`); `film init` writes `# depth: 0.5` commented.
  **Changed 2026-09-28:** `film init` now writes `depth: 0.5` ON. Jacek
  stepped What Is Love through 0.5, 0.6, 0.7, 0.8 in motion: 0.8 smeared,
  0.7 uncertain, 0.5 kept. Without onnxruntime the photos render flat
  and it says so once (render.py), so a fresh machine does not stop.
  A film without the line still means 0 (spec.py default unchanged).
- **2026-09-28:** a .png, .gif or .svg is a chart (Jacek: "charts are gif
  or png or svg, do not give those depth") and the film's `depth:` does
  not reach it (`spec.CHARTS`). A shot's own `depth:` still wins. A photo
  saved as .png would stay flat too; that is the price of the rule.
- Photographs only. Not clips (a per-frame map flickers), not the title
  card in analysis/ (it would bend the letters).
- Taste constants in moves.py: PARALLAX 1.0, PARALLAX_TRAVEL 0.1 (the
  travel counted, capped at a tenth of the window's width, so `rise`
  over a tall photo does not tear it).

## Not yet known
Whether it "looks like a place" in motion: that is for Jacek to watch on a
draft. Stills show position, not the feel of the slide. **Answered
2026-09-28:** yes, at 0.5, on What Is Love; v0.2.0 tagged.
