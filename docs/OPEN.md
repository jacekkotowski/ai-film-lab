# OPEN — faults found and not yet fixed

Every session reads this first. A fault stays here until it is fixed AND
Jacek has seen the fix work in a real render. Newest first. When fixed:
move it to the bottom section with the commit id — do not delete it.

- 2026-10-01 `columns` (a 2-column slide held, panned mid-shot, held;
  found by shape: width = 2x the frame's) is built and drafted on Excel
  Tutorial - Use tables: 7 of 7 slides got it, draft 34.5 s. Not yet
  seen by Jacek. Open: (1) `spans_the_middle` (a table across both
  halves -> slow sweep over the whole shot instead) has threshold
  SPANS_WHEN 0.20 chosen between the 4.8% measured on these slides
  (divider + arrow) and a synthetic table; no real spanning slide has
  been measured. (2) `film go`/`append_new` adds shots through
  `shots_for`, which does not look for columns: a slide dropped in
  later gets the ordinary move. (3) a 9:8 photograph would be taken
  for a slide; `move:` on the shot undoes it. (4) two faint thin
  columns at x=44,50 in a draft frame at 10.5 s, cause not found.
- 2026-09-30 last syllable of a camera take is never recorded when SPACE
  comes soon after the last word. GAM Curves intro `0_rec_20260930-200204`:
  video 16.68 s, audio 16.01 s; sound still −26..−28 dB at its last sample
  (no "-p" of "relationship"); lips close for the "p" at ~16.23 s and stay
  closed to 16.68. Start offset by lips vs sound onset ≈ 0.2 s (not the
  0.67 s `sound_lag` assumes), so ~0.45 s of sound is lost at the END
  (lips read by eye at 6–10 fps, ±0.1 s). `film.yaml` out 16.68 is the
  last frame already: no edit brings it back. fit-to-length did not cause
  it. Inferred also: this take's voice plays ~0.45 s before the lips.
  Older takes ended in ≥0.5 s silence, so the loss was hidden. Cause,
  measured with -copyts: the mic's default ~0.5 s buffer; `q` drops the
  chunk still filling. FIXED (this commit, "A take keeps its last
  syllable"): `-audio_buffer_size 50` → sound ends within 0.012 s of the
  picture; v − a now 0.24–0.27 s = the real start delay (0.28 s). Real
  take 0_rec_20260930-213940 (Jacek, 21:39): speech ends 15.51 s, then
  2.0 s at −55..−62 dB to the end; v − a 0.306. Draft c0923fb (177.7 s):
  voice ends 14.50 s, intro cut 14.75 s, music only between. Not yet
  heard by Jacek.
- 2026-09-30 "Change the words" in the recording window KEEPS the take
  just made (booth.py `edit_words` does not call `discard`); every kept
  camera take becomes a shot (GAM Curves first draft 1e9d354: three intro
  takes). Jacek: changing the words or reading again = replace the take.
  FIXED (same commit): the take is dropped to media/_discarded when the
  next take starts. Unit-tested only; the window not yet walked by Jacek.
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
- 2026-09-24 "redo one picture" was hard to find: key P (c52336d) was
  not seen either (2026-09-28). Now also menu line "Redo ONE picture
  only" (line 8 on What Is Love) and a button "Only ONE picture..." in
  the recording window — 98c638b. Window walked by a script up to the
  pick (returns the number); the reopened one-picture window and a real
  take have not been tried. **Not yet used by Jacek.**
  2026-09-29: the menu line shows once there is a narration (b601a7d);
  the window button too — before an edit its screen says so and Continue
  cuts the narration, then asks which picture. Both window paths walked
  by a script; a real one-picture take still not tried.
  2026-09-29: Jacek could not use it on It Reads Us. Two faults: (a)
  after an intro retake film.yaml named the discarded take and every
  picture recording refused ("file not found") -- fixed 37f0bd6; (b) the
  line is hidden until an edit exists, and he re-recorded the narration
  3x before the edit was made -- fixed b601a7d (offered once there is a
  narration; `record --picture` rewrites a missing or older edit first,
  measured on a copy with real takes, both cases). Sandbox for Jacek's
  test: projects/zz_redo_test (a copy of It Reads Us). Measured on a copy of It
  Reads Us, `--no-window`, real Samson take of 4 s: picture 2 re-pointed,
  only s03 changed in film.yaml, draft renders (109.6 s), and a full
  `go --rewrite` afterwards keeps the redo. The window route (menu 6 ->
  window on one picture) with a real take is still untried: Jacek tests
  it the evening of 2026-09-29.
- 2026-09-29 intro captions came out in made-up Polish (Whisper guessed
  pl, p = 0.49, from two Polish names) -- fixed 998cd67, English unless
  `--lang`. Rebuilt copy of It Reads Us: intro opens "Michał Kosiński,"
  in English. Not yet seen by Jacek in a render.
---

## Fixed (with the commit, once Jacek has seen it work)
- 2026-09-28 `render.source_maps` widened the parallax grid to float64 —
  231bdf0 (decision 0013): 98.9 -> ~41 ms/call, isolated benchmark.
  Real `film final` of What Is Love with the fix (258.9 s, 11 shots,
  depth 0.5, no profiler): **1297.5 s** wall, 550 MB. No earlier What Is
  Love final time was recorded, so the whole-film speed-up is not known.
  Other float math in the frame path checked: stays float32. Jacek:
  "fast enough".
- 2026-09-24 the check_film hook fails on a folder name with "ł" (`film
  check` itself worked run by hand) — the hook read Claude Code's event
  with Windows' own code page instead of UTF-8, so "ł" became "Å‚" and no
  folder matched. Proven on numbers: replayed the real hook on "Frankfurt
  School vs Kołakowski Emancipation and Domination/film.yaml" -- before
  the fix, "No project found"; after, `film check` reports OK, 13 shots,
  172.9s. 928 tests pass.
- 2026-09-24 last word of a camera intro/closing cut mid-vowel (caused
  by c802fcd) — 2881ea5. Proven on numbers, not by ear (Jacek judges
  sound by numbers): What Is Love, cut after 2881ea5, draft 1a74892,
  50 ms RMS. s01 end (20.70 s): speech falls from -22 dB 0.35 s before
  the cut to -44..-48 dB in the last 0.2 s. Film end (259.00 s): -22 dB
  0.40 s before, -49..-57 dB in the last 0.2 s. Bauhaus before the fix
  had -11.5 dB in the last 54 ms. Bauhaus's own hand fix (d93b059) never
  heard: old footage, skipped.
- 2026-09-28 v0.2 parallax (`depth:`), built 154cf49, tagged v0.2.0.
  Jacek watched What Is Love (7 photos, s02-s08) in motion at 0.5, 0.6,
  0.7, 0.8 (drafts 1cd1859, 3096f2b, ea53b44, fdbaf33): 0.8 smears
  (shot not named), 0.7 uncertain, 0.5 kept (1a74892): "it is ok".
  `film init` now writes `depth: 0.5` on (decision 0013). Still true at
  the time: +85 % final render time (234 -> 433 s on 4 photos). Bauhaus
  (2ddee70) never watched: old footage, skipped.
- 2026-09-28 WON'T REDO (Jacek: old films are done): the clipped last
  camera word in films cut before 2881ea5 (Turn Heat, Trade Behind War
  and older) is left as it is. 17 old films removed from projects/;
  their thumbnail and title pictures kept in archive/thumbnails/.
- 2026-09-24 lips drift ±0.5 s in a FINAL (camera's varying frame rate;
  drafts hide it) — 646de5c. Measured on the take (−0.017 s) and in the
  Frankfurt final (−0.02–0.00 s). 2026-09-28 Jacek watched the What Is
  Love final (259.1 s): "lips look fine". Every final with a camera take
  made before 646de5c keeps the drift until re-rendered.
- 2026-09-28 `film caption` dropped a script line whose names were
  misheard ("In one study,", "A 2018 meta-analysis by Kathrin Karsay,"
  on What Is Love); misheard words were counted as a false start —
  eec1145. What Is Love 361 -> 371/371 script words captioned; `film
  check` now names half a sentence on screen. Re-captioned and drafted,
  a8cd38d. Jacek watched it: "captions look right now". Note: `film
  caption --apply` ADDS to existing captions; remove them first.
  Earlier films keep their old captions until re-captioned.
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
