---
name: investigate
description: Find the cause of a fault before fixing anything — a noise in the sound, a frozen or black picture, a render that is slow, a clip that disappears. Measure first, name the mechanism second, propose a fix third. Use whenever something "sounds wrong", "looks wrong", "is slow", or "used to work".
---

# Investigate: measure, then explain, then propose

In this repo, reasoning from the code alone has given four confident,
wrong answers. Each one cost the user a whole instruction, because they
act on numbers straight away. This skill exists to stop a fifth.

## Steps

1. **Write down the claim to test**, in one sentence, before you open any
   code. "The room noise rises towards the end of the take."

2. **Check what has already been settled.** Read `docs/decisions/`. If the
   idea is listed there as a measured dead end, say so and stop.

3. **Rule out the world before the code.**
   - Did someone else change the tree? `git diff --stat` and `git log -5`.
     The guide's `[C]` option runs another Claude on these same files.
   - For recording faults: which camera and microphone were used? A
     virtual camera can deliver a frozen placeholder that records
     "perfectly". Is the Windows mic level where it was? Conferencing apps
     move it.

4. **Measure across the whole thing, not two points.**

   | Fault             | Measure with                                            |
   |-------------------|---------------------------------------------------------|
   | slow              | `python -m cProfile -s cumtime`, or time the real command |
   | loud / quiet      | `ffmpeg -af ebur128`, `volumedetect`                    |
   | noise             | band-split RMS per 15 s block; render with music off (it masks the room) |
   | frozen picture    | per-frame mean brightness: identical values mean frozen |
   | seeing it         | `showspectrumpic` for sound; a frame grab for picture   |

   Keep scratch scripts and outputs in the scratchpad, not the repo.

5. **Report as a table of numbers**, then the mechanism, with each
   sentence marked *measured* or *inferred*. If the claim from step 1 was
   wrong, say that first.

6. **Propose; don't fix.** A fix to `ffilm/` is the `change-the-machine`
   skill, and it needs the user's go-ahead. The sound chain needs an
   explicit request (see `ffilm/CLAUDE.md`).

7. **If the finding will matter again, record it** as a new file in
   `docs/decisions/`: the question, the numbers, the decision.

## Done when

The user has a measured cause, or a measured statement that the
suspected cause is *not* it, and knows what the next step would cost.
