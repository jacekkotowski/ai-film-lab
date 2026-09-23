# Pillow, and which pictures the film reads

The list is `kinds.STILL` (+ `kinds.HEIC`) — one list, used by ingest,
the menu, checks and render.

| Type | Read as a picture? |
|---|---|
| jpg, jpeg, **jfif**, png, webp, tif, tiff, bmp, heic, heif | yes |
| gif | no — only as a thumbnail backdrop (`kinds.POSTER`) |
| svg | no — neither Pillow nor OpenCV renders it; save as png first |

- 2026-09-23: `.jfif` (JPEG saved by browsers) was missing; the narration
  window showed 4 of 6 pictures. Measured after the fix: both .jfif files
  open as `JPEG` in Pillow and in OpenCV.
- A file of a type not in the list is left out **silently**.
