# 0015 — Pauses are cut in a copy of the narration, not in the sound chain

**Date:** 2026-10-05
**Status:** built; draft heard by nobody yet

## What was decided

`film tighten` shortens every pause of 0.6 s or more inside a narrated
picture to 0.4 s by writing a shorter COPY of the narration to
`analysis/tight/` and moving film.yaml's `in`/`out` and caption times
onto it. Camera takes are not tightened. `MAX_SPEED` stays 1.25.

## Why

- A slide has one `in`/`out`, so no film.yaml edit could reach a pause
  inside one picture's words.
- `audio.py` is settled (0003). A copy changes no line of it: the chain
  plays a shorter file the same way.
- The copy is named by a hash of its source and cuts and never
  overwritten, so `film undo` returns to numbers that still match a file.
- Camera takes: longest pause 0.90 s on SUMIFS, 2.0 s saveable in all,
  each cut a jump in the face. Not worth it.
- Speed: atempo round-trip distortion shows no knee from 1.15 to 1.5
  (docs/tech/audio.md), so there is no measured reason for a new ceiling.

## Measured (SUMIFS SUMPRODUCT vs DAX)

29 pauses cut, 15.95 s of recording; film 200.3 s -> 187.0 s (draft
measured 187.000 s). Joins at most -41.2 dB. 290 of 305 re-transcribed
words within 0.2 s of where the mapping put them.
