# Tech notes — by area, and by tool

**Policy (2026-09-23):** before working in an area, read its file. After,
add what was measured, the snippet that worked, what failed, and the date.
Web documentation read → saved in the tool's file (a hook reminds).
A fault not yet fixed → `docs/OPEN.md`, not here.

## Areas
| File | What |
|---|---|
| [[sync]] | lips vs sound: the cause, the fix, how to measure, wrong turns |
| [[recording]] | devices, takes (intro/narration/closing), retakes, texts |
| [[video]] | picture types, crop, moves (`rise`), render checks |
| [[audio]] | levels, noise, music, speed — mostly settled decisions |
| [[captions]] | transcription, spelling, timing, checks |

## Tools
| File | What |
|---|---|
| [[ffmpeg]] | dshow recording, measuring sound, filter order |
| [[opencv]] | Windows paths, the 5.0 trap |
| [[pillow]] | picture types read / not read |
| [[faster-whisper]] | the caption model |
| [[agent-memory]] | vector search vs a code-to-test map, the TDAD numbers |
| [[qmd]] | local markdown search + MCP server: install, models, Windows traps (not installed) |
| [[qmd-bench]] | 10 questions with known answers: grep vs qmd, scored the same way |

## Code
[[code-map]] — which file and function decides what. Read 5 lines, not
a 1,500-line file.

Files stay the home of every fact. Since 2026-09-24 they are also
searched by meaning with qmd ([[qmd]]): a name finds a file you know,
qmd finds one that uses other words ([[qmd-bench]]).
