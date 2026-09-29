# 0014 — How do ai-film-lab and ai-3d-studio work together?

**Status:** settled 2026-09-29  ·  **Commit:** 727bcf2 (film-lab side)

## The question
Both repos work on the same material. ai-film-lab (stage 1) makes the
film; ai-3d-studio (stage 2) flies it in 3D and depends on what stage 1
knows. Where does each fact live, and who may change what?

## The answer: two stages, one hand-off
```
stage 1 ai-film-lab                     stage 2 ai-3d-studio
film.yaml -> film final ==> out/final.mp4          ==> stops.json -> flight
                            out/final.timeline.json
```
1. **Stage 2 reads only the hand-off:** `final.mp4` and
   `final.timeline.json`. Never `film.yaml`, `analysis/` or `media/`.
2. **Stage 2 never writes into stage 1.** A need goes into this repo's
   `docs/OPEN.md`; stage 1 adds it to the timeline.
3. **Stage 2 records what it used:** `stops.json` keeps the timeline's
   `video_sha256`, and `fly.py` says so when the film changed since.
4. **One name per film:** `slug`, written by stage 1
   (`timeline.slug`). Stage 2 files it as `<yyyy-mm>_<slug>`.
5. **The contract is owned here.** Adding a key keeps `VERSION`;
   renaming or dropping one bumps it. Stage 2 refuses a version it
   does not know.

## The contract (version 1)
Keys stage 2 reads, pinned by
`tests/test_the_final_film_says_where_every_shot_is.py::test_the_keys_the_next_stage_reads_are_all_there`:
- film: `version, slug, video, video_sha256, title, fps, width, height, frames, shots`
- shot: `role, kind, src, title, start_frame, end_frame` (end exclusive)

## Why not one repo
Stage 1 promises four packages (0001); stage 2 runs Blender's own
Python. Separate repos keep each one's rules and tests its own. The
coupling is one file with a version number.

## Measured
What Is Love (727bcf2): a fresh export equals the existing timeline
except `slug` and `video_sha256`; hashing the 550 MB `final.mp4` took
1.66 s. Before this, all four flights matched their film frame for frame
(What Is Love 6217/6217, Trade Behind War 3653/3653, AI on my terms
3064/3064, It Reads Us 3254/3254): the link worked; nothing checked it.
