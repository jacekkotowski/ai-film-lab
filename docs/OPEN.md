# OPEN — faults found and not yet fixed

Every session reads this first. A fault stays here until it is fixed AND
Jacek has seen the fix work in a real render. Newest first. When fixed:
move it to the bottom section with the commit id — do not delete it.

## 1. Lips drift from the sound in camera takes (intro, closing)
- **Found:** 2026-09-23, "Turn Heat Into Images" (published). Also the
  Bauhaus closing on 2026-09-21 — decision 0011 measured the wrong thing.
- **Measured:** in every `rec_` take the sound is shorter than the picture:
  intro 12:30 14.10 s picture / 13.52 s sound (−4.1 %), closing 12:42
  21.88 / 21.51 (−1.7 %), an older take 15.47 / 14.51 (−6.2 %). Both start
  at 0. The camera says 60 fps, delivers ~43, unevenly.
- **Inferred, not measured:** the gap grows through the take — in sync at
  the start, sound up to ~0.5 s ahead of the lips at the end.
- **Not the cause:** the 1.2 speed (it is applied to picture and sound alike).
- **Fix proposed, waiting for Jacek's yes** (touches `audio.py`, which he
  asked to be left alone): stretch each camera take's sound to its picture
  length at build time; and keep them in step while recording
  (`record.py`). The slides narration is a separate file — not touched.

## 2. A very tall photo is cut in a vertical film
- **Found:** 2026-09-23, `4_evaporograph.jfif` (361×811, width/height 0.45)
  in a 1080×1920 film (0.56): cropped top and bottom, more by the
  `drift_right` zoom — the equipment is never seen whole.
- **Cause:** `fill: crop` fills the width. `fill: blur` exists per shot,
  but its sharp part has the film's `fill_aspect` (1.0, square), which
  would cut a tall picture even more. There is no per-shot aspect.
- **Fix to decide:** a picture narrower than the frame shows whole, with
  a blurred copy at the sides, automatically. Waiting for Jacek.

---

## Fixed (with the commit, once Jacek has seen it work)
- 2026-09-23 `.jfif` pictures missing from the narration window — 74461ac
- 2026-09-23 retaken intro/closing played twice / at the wrong end;
  intro and closing shared one text — 576fdaf, 4a2b029
- 2026-09-23 menu: intro first; back to the menu after a stopped take —
  132379c
- 2026-09-23 "file not found" after retakes — 50cd700
