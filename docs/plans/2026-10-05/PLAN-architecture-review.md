# Architecture review — plan (2026-10-05)

A review of ai-film-lab (and a look at ai-3d-studio) asked for by Jacek,
with Manim slides in view. Nothing here is done yet. Each item is one
session (`one task per session`), and each change to `ffilm/` waits for
Jacek's go-ahead (`change-the-machine`).

## Measured on 2026-10-05

| | ai-film-lab | ai-3d-studio |
|---|---|---|
| code | 16,861 lines, 27 modules | 1,097 lines, 3 scripts + 1 test file |
| largest | scaffold 2198, cli 1889, audio 1647, render 1200, booth 1154, guide 1153 | flight.py 770 |
| dependencies | 4 (+3 optional extras) | Blender's own Python |
| tests | 983 passed in 19.9 s | 6 passed in 0.02 s |
| OPEN entries | 10, of which 5 are recording / retakes | – |

## Keep as it is
- `film.yaml` as the one source; `spec.py` says what a film is.
- The layer test (imports only point down); pure-function tests named as sentences.
- `docs/decisions/`; model files checked by SHA-256.
- The hand-off to ai-3d-studio (decision 0014): one versioned file, `video_sha256` checked.
- ai-3d-studio as it is: small, one job (effects and navigation over a finished film).

## To do, in order

### 1. Narration over a clip
- **Why:** a shot has one `in`/`out`; for a video it means inside the clip, for a
  slide inside the voice file (`ffilm/spec.py`, `Shot.parse`, ~line 269–299;
  `voice` is only filled in for stills at ~298). So "this clip plays while I say
  this paragraph" cannot be written.
- **Blocks:** Manim clips from ai-manim (its PLAN step 3); screen recordings of code
  under narration.
- **Proposed:** `voice_in` / `voice_out` on a video shot. (inferred, not tried)
- **Done when:** a draft with one clip under a narrated paragraph; lips/words checked by numbers.

### 2. Move the logic out of `cli.py`
- **Why:** its own rule says new logic never goes in cli, but `cmd_record` is
  ~370 lines and `cmd_caption` ~200 (measured: lines between `def`s).
- **Proposed:** into `record` / `booth` and `caption_fit`. No behaviour change.
- **Done when:** 983 tests still pass; `cli.py` only parses and prints.

### 3. Split `scaffold.py` (2198 lines, 61 functions)
- **Why:** three jobs in one file — first draft, cutting narration into slides,
  retakes and caption surgery. Recent faults sat in the last two (discarded take
  still named in film.yaml; doubled captions). (inferred)
- **Proposed:** `scaffold` (draft), `slides`, `retakes`.
- **Done when:** tests pass; layer test updated; each file has one docstring job.

### 4. A take that hangs can be stopped
- **Why:** OPEN 2026-10-02 — when the Windows audio engine crashed, ffmpeg never
  read `q`; the window has no timeout for a take that stops writing.
- **Proposed:** a watchdog in `booth.Take`: the file stops growing for N s →
  stop, then kill, and say so. ~20 lines. (inferred)
- **Done when:** a unit test on the pure decision; one real take stopped by unplugging the mic.

### 5. Correct the docs
- `ffilm/CLAUDE.md` says the tests run "under a second"; measured 19.9 s.
- Same line in root `CLAUDE.md` ("the tests, under a second").

## Around this project (done 2026-10-05)
- `scripts/mic-level.ps1` (097f6cb): reads the Windows mic level, sets 85 % by
  default. Takes after setting it: peaks −2.3 / −0.0 / −0.7 dBFS (were −17).
- Recording start delay measured: first picture 0.88–1.14 s after launch; the
  clock waits for it on purpose (`booth.py` ~917); the 3 s is the countdown
  (`COUNT_FROM = 3`). Nothing lost from the file.
- `../ai-manim` created (a9471df): stage 0, Manim slides narrated over as stills
  here, then timed to the words (decision 0001 there). Needs item 1 above to swap
  the clip in.

## The three projects, one film
1. text — ai-film-lab `write-to-fit`
2. Manim stills — ai-manim `new-scene` → copy PNG into `media/`
3. record and cut — ai-film-lab, as now
4. Manim clips — ai-manim `time-to-words` → copy MP4 in place of the still (needs item 1)
5. flight over the plan — ai-3d-studio `FLY.bat` on `final.mp4`
