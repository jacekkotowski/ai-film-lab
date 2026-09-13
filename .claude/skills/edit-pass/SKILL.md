---
name: edit-pass
description: One round of the everyday editing loop — the user reacts to a render in plain language ("shot 3 drags", "too repetitive", "the caption is too early") and you turn each note into a small, explained edit of film.yaml, then re-render peek or draft. Use for any note about pacing, order, moves or captions of a film.
argument-hint: "[project] [notes]"
---

# Edit pass: notes in, small edits out, render again

This loop *is* the system. It is expected to go round many times, so
every pass must be small enough that the user can tell what each change
did.

Rules for this role: `projects/CLAUDE.md`. Its taste defaults apply.

## Steps

1. **Re-read `film.yaml`.** The user may have changed it in the bench or in
   Notepad++ since you last read it. *Why:* editing a stale copy silently
   undoes their work.

2. **Split the message into separate notes.** Number them back to the user
   if there is more than one. A note you can't locate in the file
   ("the bit in the middle") gets a one-line question, and the other notes
   go ahead.

3. **Translate each note into the smallest edit that answers it.**

   | The user says                 | Usually means                                  |
   |-------------------------------|------------------------------------------------|
   | "drags", "too long"           | lower `duration`                               |
   | "rushed", "hold it"           | raise `duration`                               |
   | "repetitive", "mechanical"    | vary `move` across families; add a `static`    |
   | "too much movement" (one shot) | a `drift_*` or `static` instead of a push/pan |
   | "too much movement" (whole film) | a taste constant in `ffilm/moves.py` — say so |
   | "caption too early/late"      | that caption's `at`                            |
   | "too wordy"                   | cut captions that repeat the picture           |
   | "wrong bit of the clip"       | `in`/`out`; candidates in `analysis/cuts/`     |

   Never replace explicit `from:`/`to:` windows; those were set by hand.

4. **Make the edits one note at a time**, adding or updating a `note:`
   where the reason isn't obvious. The hook runs `film check` after each
   edit. If it fails, fix that first.

5. **Render the cheapest thing that shows the change.**
   - order, durations, captions → `uv run film peek -p NAME` (seconds)
   - moves, easing, motion → `uv run film draft -p NAME` (under a minute)

   *Why:* the user's time goes to looking, not waiting. Both commands
   open a player on the user's screen when they finish; that is intended.
   Every render also commits `film.yaml`, which is what `film undo` uses.

6. **Report in this shape**, and nothing more:
   ```
   1. "shot 3 drags"   s03 duration 6.0 -> 4.2
   2. "too repetitive" s05 push_in -> static (s04 and s06 were both lateral)
   peek ready: projects/NAME/out/peek.mp4
   ```

## If the user says it got worse

Offer `uv run film undo -p NAME` first; it puts back the last version they
watched. Don't pile a repair edit on top of a bad edit.

## Done when

Every note has either a line in the report or a question, and the render
has finished. Then wait for the next note.
