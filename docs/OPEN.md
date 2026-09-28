# OPEN — faults found and not yet fixed

Every session reads this first. A fault stays here until it is fixed AND
Jacek has seen the fix work in a real render. Newest first. When fixed:
move it to the bottom section with the commit id — do not delete it.

- 2026-09-28 `film caption` silently DROPS a script line whose words
  the transcriber heard but spelled differently. What Is Love: "A 2018
  meta-analysis by Kathrin Karsay," (heard "Catherine Carcey") and "In
  one study," had no caption at all; `film check` said nothing, because
  it reads only the captions that exist. Fixed by hand in film.yaml
  (6bdf1a7) from whisper word times on the slice. **Code fixed eec1145**
  (cause: misheard words counted as a false start). Measured on whisper's
  real output: What Is Love 361 -> 371/371 script words captioned; 3
  other films unchanged, Bauhaus 4 lines extended onto speech. `film
  check` now names half a sentence on screen. **Not yet seen by Jacek
  in a render made by `film caption` with the new code.**
- 2026-09-28 v0.2 parallax (`depth:`) built, 154cf49. **Not yet seen in
  motion by Jacek**: judged only on stills (0.5 clean, 0.8 stretches, charts
  bend: decision 0013). Costs +85 % render time at final (234 -> 433 s on
  4 photos); `render.source_maps` is 59 ms a frame, untried to speed up.
  Not yet tagged v0.2.0: "Done when" needs Jacek's "looks like a place".
  First film with it: Bauhaus draft, `depth: 0.5`, 2ddee70 (65.4 s render,
  5 depth maps made). Waiting for Jacek to watch s04 s05 s06 s08 s11.
- 2026-09-25 qmd MCP fails to connect at the start of some Claude
  sessions ("recent failure cached", 15 min), while `claude mcp list` in
  the same session says Connected. qmd itself is fine since the move out
  of the app's private folder (docs/tech/qmd.md). Cause of the start-up
  failure not measured. Workaround: a new session, or `/mcp` in a
  terminal `claude`. Not yet seen working from Claudian.
- 2026-09-24 qmd MCP `query` returned `Object is disposed` on 6 calls in
  a row (right after a burst of calls that were cancelled mid-flight);
  the same calls worked on retry, and 12 later calls had no error. Cause
  not found (docs/tech/qmd-bench.md). If it recurs: retry once, then
  grep. The qmd indexes (`code`, `history`) are not refreshed by
  themselves: docs/tech/qmd.md says how.
- 2026-09-24 last word of a camera intro/closing cut mid-vowel. Caused
  by c802fcd (sound moved by the lag, cuts not). Code fixed in 2881ea5,
  Frankfurt film.yaml fixed by hand. **Not yet heard in a render.**
  Films drafted between c802fcd and 2881ea5 (Turn Heat, Trade Behind War)
  keep the old cuts until their intro/closing `out:` is moved by ~0.6 s.
  2026-09-28: Bauhaus (cut 09-19, before both) had it on all 5 camera
  shots, 0.34-0.42 s of each last word lost ("community" at the end,
  Jacek heard it). Every take `in`/`out` moved +lag (0.62 / 0.59 s), last
  `out` 58.30 -> 59.00. Draft d93b059: last 0.3 s now -45..-69 dB (was
  -11.5 dB in the final 54 ms). **Not yet heard by Jacek.** Other films
  cut before 2881ea5 still need the same check.
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
- 2026-09-24 music went silent at the last word (ducking stops with the
  speech) — 878207e. Happy Birthday final: -25..-33 LUFS over the 20 s
  closing card (was -55.4). Jacek heard it: "it works". Earlier films
  that end on a silent picture keep the silence until re-rendered.
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
