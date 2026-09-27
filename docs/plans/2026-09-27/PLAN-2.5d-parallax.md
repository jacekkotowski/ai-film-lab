# v0.2 — photographs with depth (2.5D parallax)

**Status: PLANNED 2026-09-27.** Milestone v0.2 on GitHub. v0.1.0 is the
2D film as it stands today.

## Why

The camera over a photograph is a crop window sliding across a flat
picture (`render.warp`: one affine map per frame). Every pixel moves
together. In a real camera move the near things slide past the far ones,
and that difference is what makes a still look like a place. A depth map
of the photo is enough to fake it: as the window moves, shift each pixel
by how near it is. That is 2.5D: still one photo, no 3D scene.

It has to happen here, on the source photo, and not later on the rendered
film: there the captions and grain are baked in, the crop leaves nothing
to reveal behind the foreground, and a per-frame depth flickers. (Why not
in Blender or ai-3d-studio: `ai-3d-studio/PLAN.md`, "Later".)

## What already exists (read from the code, not run)

- **The move is data.** `moves.window_at(shot, t, seed)` gives the
  window for any moment; `shot.focus` says where the subject is. Parallax
  can reuse both: the window's travel is the camera's travel, and the
  focus point is the depth that stays put.
- **Bokeh is the pattern to copy.** `segment.py` runs a model with
  OpenCV's own `cv2.dnn`: no new package, only a model file fetched once
  through `models.CATALOGUE`, checked by SHA-256, listed in
  `models/README.md`. A film-level `bokeh:` with a per-shot override,
  recordings only; `checks.bokeh_notes` tells you what will happen.
  Depth is the same shape: film-level `depth:`, per-shot override,
  **photographs only**.
- **Derived files live in `analysis/`**, named by `ingest.analysis_keys()`,
  regenerable, in `.gitignore`: proxies, the title card. A depth map is one
  more of these.
- **`render.should_memoise`** reuses a still's frame when the camera does
  not move. With depth and a moving window every frame differs, so a
  parallax shot costs a real warp per frame, like a clip does now.

## What would be built

1. **Depth for one photo: `ffilm/depth.py`, layer 4 beside `segment.py`.**
   Depth Anything V2 **Small** (Apache-2.0; Base and Large are
   non-commercial, so they are out for a public toolkit). Photo in, depth
   out, normalised 0 far .. 1 near, lightly blurred so edges stretch
   instead of tearing. Cached as `analysis/depth/<key>.png` (16-bit), made
   on first need and never again unless the photo changes.
   **Runner, decided by measuring (step 0):** `cv2.dnn` if it loads the
   model and gives the same depth as the reference, otherwise
   `onnxruntime` as an optional extra (`uv sync --extra depth`, the way
   `voice` is). Without it, the film renders flat and says so once, as a
   missing model does now.
2. **The model in `models.CATALOGUE`** + `models/README.md` row (a test
   keeps them equal). A decision record, `docs/decisions/0013-which-model-for-depth.md`,
   says which file (fp32 / fp16 / quantised), its size and ms/photo on
   this PC, and why.
3. **`depth:` in film.yaml**: film-level default, per-shot override, 0 =
   flat (today's picture, exactly). Ignored on clips. Parsed in `spec.py`
   like `bokeh`. `film init` writes a commented `# depth: 0.5` line in
   the header, so it is found where bokeh is found. **The default stays 0**:
   a chart or a screenshot has no depth to give, and nobody's existing
   film may change under them.
4. **The camera with depth: in `render.py`.** A pure function builds the
   remap for one frame: the window's affine map as today, plus each
   pixel's shift = (window centre's travel from mid-move) x strength x
   (its depth - the depth at `shot.focus`). The subject stays locked,
   what is nearer moves more, what is farther moves against it. Then
   `cv2.remap`. Zoom moves (push in, pull out) scale near pixels a little
   more than far ones, the same way. `depth: 0` takes the existing
   `warp` path untouched.
5. **The bench keeps it.** `editor.py` hands every shot back field by
   field (see `dissolve`, `voice`); `depth` joins that list, or the first
   Save wipes it.
6. **`film check` says it**: which shots get depth, whether the runner
   and model are there, the same as `bokeh_notes`.
7. **Version 0.2.0** in `pyproject.toml`, tag `v0.2.0`, release notes.

## Tests (pure; sentence names)

- `test_a_photo_with_no_depth_is_the_same_picture.py`: `depth: 0` output
  is bit-identical to today's `warp`, for every move.
- `test_the_subject_stays_where_the_camera_looks.py`: the pixel at
  `focus` does not shift; nearer shifts more than farther; farther moves
  the other way; mid-move is zero shift.
- `test_depth_is_for_photographs.py`: parsed at film and shot level, the
  shot wins, clips ignore it, the bench round-trips it.
- The layers test gets `"depth": 4`; the model catalogue test covers the
  new model.

## Risks to check before building (measure, don't assume)

- **Step 0, the runner.** Load Depth Anything V2 Small in `cv2.dnn` on
  this PC. Compare its depth with onnxruntime's on 3 photos (mean abs
  difference), time both. That decides whether 0.2 needs a new package.
- **Render time.** `remap` instead of `warpAffine`, and no memoising on
  parallax shots. Profile a final with cProfile, as in decision 0002, and
  report seconds before and after. warpAffine was 11 % of a final.
- **Edges.** Where near meets far, the shift reveals what was hidden. Try
  strengths 0.3 / 0.5 / 0.8 on 3 real photos, stills at the extremes of
  the move, and judge the edges on stills, not on a feeling.
- **A photo that is not a photo.** Run depth on a chart and a screenshot
  once, to see whether it is harmless at 0.3 or visibly warps, so the
  advice in film.yaml's header is measured.

## Cost

About 7 pieces, each with a test. New module `depth.py`; changes to
`render.py`, `spec.py`, `models.py`, `editor.py`, `checks.py`,
`scaffold.py` (the header line). `audio.py` untouched. At most one new
package (`onnxruntime`, optional), only if step 0 says `cv2.dnn` can't.

## Done when

A photo film rendered with `depth: 0.5` looks like a place on stills and
on a draft, a film with no `depth:` renders the same frames as v0.1.0, all
tests pass, and v0.2.0 is tagged.
