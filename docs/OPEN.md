# OPEN — faults found and not yet fixed

Every session reads this first. A fault stays here until it is fixed AND
Jacek has seen the fix work in a real render. Newest first. When fixed:
move it to the bottom section with the commit id — do not delete it.

(nothing open)

---

## Fixed (with the commit, once Jacek has seen it work)
- 2026-09-23 lips drift from the sound in camera takes — c802fcd.
  Cause measured: the microphone starts 0.849 s after the camera; fixed by
  `audio.sound_lag` (intro +40 ms, closing −80 ms, were −483 / −314 ms).
  Jacek watched the Turn Heat draft: "good enough", accepted provisionally
  — reopen if it shows again. **Still not measured:** that picture and
  sound stop together at the end of a take.
- 2026-09-23 a very tall photo is cut in a vertical film — 78801ad.
  Move `rise` (bottom to top, no zoom) for photos >10% narrower than the
  frame. Jacek watched `4_evaporograph.jfif`: it stays longer at the
  bottom, then travels to the top; "looks good", accepted provisionally.
- 2026-09-23 `.jfif` pictures missing from the narration window — 74461ac
- 2026-09-23 retaken intro/closing played twice / at the wrong end;
  intro and closing shared one text — 576fdaf, 4a2b029
- 2026-09-23 menu: intro first; back to the menu after a stopped take —
  132379c
- 2026-09-23 "file not found" after retakes — 50cd700
