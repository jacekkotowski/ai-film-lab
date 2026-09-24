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

## Code
[[code-map]] — which file and function decides what. Read 5 lines, not
a 1,500-line file.

Why files and not a vector database: at tens of files a name finds the
right one exactly. Add semantic search when there are hundreds.
