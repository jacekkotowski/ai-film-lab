# OpenCV (`opencv-python-headless`)

- **Never call `cv2.imread` / `cv2.imwrite` directly — use `ffilm/pix.py`.**
  On Windows OpenCV cannot open a path with non-ASCII letters (Polish
  names) and says so only by returning `None`.
- **Pinned below 5.0.** 5.0 removed `CascadeClassifier`, which silently
  switched off face detection. `uv.lock` is tracked for this reason
  (decision 0001).
- Reads .jpg/.jfif/.png/.webp/.tif/.bmp. Does **not** read .gif or .svg.
- **`cv2.dnn` (4.14) cannot load Depth Anything V2.** Measured 2026-09-28:
  onnx-community's fp32/fp16 refuse with `dynamic 'zero' shapes are not
  supported`, its int8 on a Reshape node, and fabio-sim's fixed 518x518
  export because it cannot build the custom layers. Depth runs in
  onnxruntime instead (decision 0013). It does load MediaPipe's selfie
  `.tflite` (bokeh, 0006).
- `cv2.remap` wants float32 maps; `cv2.invertAffineTransform` of the
  `getAffineTransform` matrix gives the output-to-source map `warpAffine`
  uses internally (render.source_maps).
