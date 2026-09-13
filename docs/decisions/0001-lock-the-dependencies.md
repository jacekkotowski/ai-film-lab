# 0001 — Why is `uv.lock` tracked in git?

**Status:** settled  ·  **See also:** `.gitignore`, `pyproject.toml`

## The question
Many Python projects ignore their lock file and rely on version ranges in
`pyproject.toml`. Why does this one commit `uv.lock`?

## What happened
`opencv-python-headless>=4.9` quietly resolved to OpenCV 5.0 on a fresh
machine. 5.0 removed `CascadeClassifier`. Face detection stopped working
**without an error**: shots with faces simply stopped getting their longer
durations, and nobody noticed for weeks.

## The decision
- `uv.lock` is committed and travels with the code (and with `film pack`).
- `pyproject.toml` pins OpenCV below 5 (`<5`), with a comment pointing at
  `ingest.faces_available`.
- Four runtime dependencies: numpy, opencv, pillow, pyyaml. Anything else
  is an optional extra (`voice`) or dev-only (`dev`).

## Reopen it only if
OpenCV 5 gains an equivalent face detector *and* a test proves
`faces_available()` still finds faces on the new version.
