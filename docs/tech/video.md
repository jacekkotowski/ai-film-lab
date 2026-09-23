# Video — pictures, crops, camera moves, render

## Which pictures are read
jpg, jpeg, jfif, png, webp, tif, tiff, bmp, heic, heif (`kinds.STILL`).
**gif and svg are left out silently** — save as png. (.jfif added 74461ac.)

## Crop and moves
- `fill: crop` (default) fills the frame and loses the overflow;
  `fill: blur` per shot keeps a sharp part (film's `fill_aspect`) over a blur.
- Focus detection (faces/saliency) decides WHERE the camera aims, never
  how much fits.
- **Tall picture** (narrower than the frame by >10%): render gives it
  `rise` — bottom edge to top edge, widest window, no zoom (78801ad).
  Opt out: `move: static` or `from:`/`to:`.
- Moves: push_in pull_out pan_* tilt_* drift_* punch_in reveal static rise.
  Only SETTLE (0.85) of a move is shown. `render.warp` clamps the window
  inside the image — aim past an edge to land on it.
- Explicit camera: `from: {cx, cy, scale, roll}` / `to:` (0..1 of source).

## Render
- Where time goes and what does NOT speed it up: decision 0002.
- Bokeh model: decision 0006 (invisible in vertical close-ups).
- Checking a frame: `ffmpeg -ss T -i out/draft.mp4 -frames:v 1 f.png`,
  then LOOK at it — that is the proof, not the code.

## Tools
[[opencv]], [[pillow]], [[ffmpeg]].
