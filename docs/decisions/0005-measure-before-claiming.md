# 0005 — Why does every Claude session here have to "measure before claiming"?

**Status:** standing rule since 2026-09-10  ·  **Enforced by:** the
`investigate` skill, and `ffilm/CLAUDE.md`

## The question
Why a rule so strict that Claude must profile or measure before saying
where a cost or fault lies, even when the code "clearly" shows it?

## Four confident, wrong answers from reading the code

| Claimed                                                   | Measured                                        |
|-----------------------------------------------------------|-------------------------------------------------|
| 62 % of video decodes are redundant                       | 0.3 %; the shutter was already adaptive         |
| `preset slow` is free because the encoder is starved      | true at 3 fps; at 6 fps it cost 21 % for a 2 % smaller file |
| Parallel shot rendering is "the route to real speed", 3–4× | zero; 84 % more CPU, same wall clock           |
| Room noise rises towards the end; the speaker gets quieter | neither; a full sweep contradicted both        |

Each answer was plausible, specific and numeric, which is exactly why each
one was acted on.

## Why it matters more here than usual
The person using this repo is a data scientist. They read numbers, act on
them straight away, and don't re-check the arithmetic. A confident wrong
number costs a whole instruction, and a run of them made the project feel
as if it was getting worse.

## The decision
- Profile (`cProfile`) or time before naming a performance cost.
- Measure with ffmpeg across the **whole** take before naming a sound
  mechanism.
- In every answer, mark each claim as *measured* or *inferred*.
- When a premise turns out wrong, say so **first**, before doing the work.

## Reopen it only if
Never, really. This rule is the cheapest one in the repo.
