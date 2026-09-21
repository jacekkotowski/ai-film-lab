# Decisions

Each file here answers one question that cost real time to settle, so it
never has to be settled again. They are short and they carry the numbers.

**Read the list before proposing a change.** If your idea is here as a
dead end, you need *new* measurements to reopen it, not a new argument.

| #    | Question                                              | Answer, in a line                                  |
|------|-------------------------------------------------------|----------------------------------------------------|
| 0001 | Why is `uv.lock` in git?                              | A version range silently removed face detection    |
| 0002 | Where does render time go, and what doesn't help?     | `apply_look`; four ideas measured worthless        |
| 0003 | Why is there room noise late in a take, and what fixed it? | A gate on the wrong scale; a second gate before the expander |
| 0004 | Why does a recording come out frozen, quiet or hissy? | The device and the room, not the code              |
| 0005 | Why "measure before claiming"?                        | Four confident wrong answers from reading code     |
| 0006 | Which model finds the person for bokeh?               | MediaPipe landscape; +45 % on final; unseen in tall close-ups |
| 0007 | Why is every music track at -20 LUFS, and how does it repeat? | Measured once; trimmed 18 dB under its loudness; 5 s crossfade |
| 0008 | Which speech denoiser, where, and how is it installed? | RNNoise sh after both gates (before speechnorm hangs); fetched and checked into models/ |
| 0009 | How does a new skill get written?                     | After the job was done once for real; copy `fit-to-length`'s shape |
| 0010 | Should narration read over photographs be sped up too? | Yes: one film, one voice, 1.2 on everything spoken. `speed:` on a slide had been a dead key |
| 0011 | Were the lips out of sync in the Bauhaus closing?     | No. Picture and sound within 40 ms; the shot was at 1.0, not the 1.22 blamed |

## Writing a new one

Copy this, number it next, and keep it under a page:

```markdown
# NNNN — The question, as a question?

**Status:** settled YYYY-MM-DD  ·  **Commits:** abc1234

## The question
What was asked, and by whom, in one paragraph.

## What was measured
The table of numbers. Say how each was measured.

## The decision
What was chosen, and what that rules out.

## Reopen it only if
The specific new evidence that would change the answer.
```

*Why this format:* in industry these are called ADRs (Architecture
Decision Records). What makes them useful is the last section. It turns
"we tried that" into a condition someone can actually check.
