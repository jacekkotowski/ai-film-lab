# Architecture review — ai-film-lab (2026-10-05)

**Status:** findings, not a to-do list. Nothing here is agreed. No change
to `ffilm/` is made from this file unless Jacek asks for it by name.
Needs of other projects (ai-manim, ai-3d-studio) are not findings here:
they enter `docs/OPEN.md` only when Jacek agrees (ai-manim CLAUDE.md).

## Measured
| | |
|---|---|
| code | 16,861 lines, 27 modules |
| largest | scaffold 2198, cli 1889, audio 1647, render 1200, booth 1154, guide 1153 |
| dependencies | 4 (+3 optional extras) |
| tests | 983 passed in 19.9 s |

## Keep as it is
- `film.yaml` as the one source; `spec.py` says what a film is.
- The layer test (imports only point down); pure-function tests named as sentences.
- `docs/decisions/`; model files checked by SHA-256.
- The hand-off to ai-3d-studio (decision 0014), and ai-3d-studio itself.

## Findings

### 1. A take that hangs cannot be stopped (recording fault)
- OPEN 2026-10-02: after a Windows audio crash, ffmpeg never read `q`;
  the window has no timeout for a take that stops writing. Seen once;
  cause of the crash not measured.
- Option: a watchdog in `booth.Take` — file stops growing for N s →
  stop, then kill, and say so. ~20 lines. (inferred, not tried)
- Jacek's decision.
- DONE 2026-10-05 (c9a6239): stop after 5 s without growth, kill 5 s
  later. Proved on a stand-in process; not yet on a real hang.

### 2. Wrong text in the docs (no code)
- `ffilm/CLAUDE.md` and root `CLAUDE.md` say the tests run "under a
  second"; measured 19.9 s.
- DONE 2026-10-05: both now say "about 20 seconds" (re-measured 23.1 s
  wall, uv start-up included; 983 passed).

### 3. Code tidiness (no behaviour change; benefit inferred)
- `cli.py` breaks its own rule (no logic in cli): `cmd_record` ~370
  lines, `cmd_caption` ~200.
- `scaffold.py` holds three jobs: first draft, cutting narration into
  slides, retakes and caption surgery.
- Only if Jacek wants it. The films do not need it.
- DONE 2026-10-05 (9c7c6b7): scaffold split into scaffold 1314 / slides
  690 / retakes 239; first draft byte-identical on 4 projects.
- NOT DONE: cli.py. No test calls `cmd_record` (371 lines) or
  `cmd_caption` (196); moving them is a rewrite of closures, provable
  only by recording and captioning for real. Waits for Jacek.

## Starting a new film
Nothing above blocks it. Before recording:
- set the microphone: `scripts/mic-level.ps1` (85 % by default);
- a take that hangs still cannot be stopped from the window (finding 1).
