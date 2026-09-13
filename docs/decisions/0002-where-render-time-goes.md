# 0002 — Where does `final` render time go, and what doesn't help?

**Status:** settled 2026-09-12  ·  **Commits:** 8627f2c, 302a212, 5e4c58d, a568c7b

## The question
`film final` was slow. What is actually expensive, and which of the obvious
speed-ups are worth building?

## What was measured
Profiled with `cProfile` on a 288-frame final render: 92.7 s before the
fixes, 40.4 s after.

| Where                | before | after | note                                  |
|----------------------|-------:|------:|---------------------------------------|
| `apply_look`         |  43 %  |  52 % | still the biggest                     |
| `draw_captions`      |  35 %  |   —   | fixed: caption art drawn once, cached |
| `warpAffine` (camera)|   5 %  |  11 % | the camera itself is cheap            |
| video decode         | 2.4 %  |   4 % |                                       |

`_glow`'s Gaussian blur now runs at quarter scale. The picture was verified
unchanged by PSNR.

## Four dead ends — measured, not argued

1. **Caching redundant video decodes.** The shutter is already adaptive
   (`render.motion_px`): on a drift-heavy film 99.6 % of frames use a single
   sub-frame. Worth about 0.3 % of 2.4 %.
2. **Lowering the shutter cap.** Worth nothing, for the same reason.
3. **A faster x264 preset.** The encoder sits blocked on the pipe, so the
   preset buys file size, not time. CRF 17, measured twice:

   | preset   | time   | size     |
   |----------|-------:|---------:|
   | veryfast | 37.7 s | 29.47 MB |
   | fast     | 40.6 s | 31.21 MB |
   | medium   | 41.7 s | 29.77 MB |
   | slow     | 51.1 s | 29.10 MB |

   `medium` is set: about the same wall clock as `fast`, 4.8 % smaller.
4. **Rendering shots in parallel.** Built, measured, removed (a568c7b). On six
   cores: one process 72.9 s / 69.2 s at ~305 % CPU; six processes
   68.3 s / 69.9 s at ~561 % CPU. 84 % more processor for the same finish
   time, and three workers were slower than one. **The render is limited
   by memory bandwidth, not by the number of cores.**

## The decision
Stop here. The one route left is fewer passes over each frame inside
`apply_look`: folding saturation, tone, lift and flicker into a single
LUT-and-blend. It is worth roughly half of that 52 %. It has not been
attempted, because `final` is run rarely.

## Reopen it only if
A profile of a *current* render shows a different distribution, or the
user says final-render time has become a problem in practice.
