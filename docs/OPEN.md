# OPEN — faults found and not yet fixed

Every session reads this first. A fault stays here until it is fixed AND
Jacek has seen the fix work in a real render. Newest first. When fixed:
move it to the bottom section with the commit id — do not delete it.

- 2026-09-24 music went silent at the last word (ducking stops with the
  speech). Fixed in audio.duck_filters; Happy Birthday peek measured
  -25..-33 LUFS over the 20 s closing card (was -55.4). **Not yet heard
  by Jacek.** Every earlier film that ends on a silent picture has this.

- 2026-09-24 last word of a camera intro/closing cut mid-vowel. Caused
  by c802fcd (sound moved by the lag, cuts not). Code fixed in 2881ea5,
  Frankfurt film.yaml fixed by hand. **Not yet heard in a render.**
  Films drafted between c802fcd and 2881ea5 (Turn Heat, Trade Behind War)
  keep the old cuts until their intro/closing `out:` is moved by ~0.6 s.
- 2026-09-24 lips drift ±0.5 s in a FINAL (camera's varying frame rate;
  drafts hide it). Fixed 646de5c, measured on the take (−0.017 s) and in the
  Frankfurt final (frames matched to the take at 3–23 s: −0.02–0.00 s).
  **Not yet seen in a final by Jacek.** Every earlier final with a camera
  take has this drift.
- 2026-09-24 "redo one picture" was hard to find: now key P in the
  menu (c52336d). The P → pick → window path has not been walked.
- 2026-09-24 the check_film hook fails on a folder name with "ł" (the
  path is garbled); `film check` itself works when run by hand.

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
