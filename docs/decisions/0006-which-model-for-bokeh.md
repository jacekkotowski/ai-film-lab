# 0006 — Which model finds the person for bokeh, and what does it cost?

**Status:** settled 2026-09-15  ·  **Commits:** 561865c, and the bokeh commit after it

## The question
Jacek asked for bokeh on recorded takes: the speaker sharp, the room behind
softly blurred. Not `fill: blur`, which blurs a copy of the whole picture.
It needs a mask of the person in every frame, without a fifth package.

## What was measured
OpenCV 4.14's `cv2.dnn` runs both candidates. They were tested on "I love you",
`rec_20260910-173831.mp4`, 240 frames from 1:00, 1920x1080.

| model                               | file    | infer ms (median/p95) | edge shimmer raw → smoothed | what it got wrong |
|-------------------------------------|--------:|----------------------:|-------------------:|-------------------|
| MediaPipe `selfie_segmenter_landscape` | 250 KB | 10.8 / 12.8 | 0.055 → 0.029 | a little of the hat brim goes soft |
| OpenCV zoo PP-HumanSeg 2023mar      | 6.2 MB  | 18.3 / 22.2 | 0.030 → 0.015 | kept the hanger and shirt on the door sharp, as a "person" |

Shimmer is the mean frame-to-frame change of the mask where it is between 0.1
and 0.9. Smoothing is each mask averaged 50/50 with the previous one. The
figure includes real head movement, so it only compares the two models.

Real render cost: `film final` on "Prayer for Her" s01+s02 (371 frames at 1920x1080),
one run each:

| quality | bokeh 0 | bokeh 1 | added |
|---------|--------:|--------:|------:|
| draft   | 49.1 ms/frame | 79.7 ms/frame | +62 % |
| final   | 154.0 ms/frame | 223.7 ms/frame | +45 % |

## The decision
- MediaPipe landscape. A wrong object left sharp is worse than a steadier edge.
- `bokeh:` is a number: 0 means off, which is the default. The film sets it, and a
  shot may override it. It applies to video only. The mask is smoothed across decoded frames.
- The model lives in `models/`, which git ignores except `models/README.md`
  (URL, SHA-256). A film that asks for bokeh without the model is told
  so by `film check` and by the render. Nothing is skipped silently (see 0001).
- It does almost nothing in vertical films of close-up takes. The 9:16 crop
  keeps 32 % of the width, and in those takes that strip is nearly all face.

## Reopen it only if
- A take where MediaPipe's edge visibly shimmers or cuts off hair and shoulders, seen in a render.
- Or a model that beats both rows above on the same 240 frames.
