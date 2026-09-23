# OpenCV (`opencv-python-headless`)

- **Never call `cv2.imread` / `cv2.imwrite` directly — use `ffilm/pix.py`.**
  On Windows OpenCV cannot open a path with non-ASCII letters (Polish
  names) and says so only by returning `None`.
- **Pinned below 5.0.** 5.0 removed `CascadeClassifier`, which silently
  switched off face detection. `uv.lock` is tracked for this reason
  (decision 0001).
- Reads .jpg/.jfif/.png/.webp/.tif/.bmp. Does **not** read .gif or .svg.
