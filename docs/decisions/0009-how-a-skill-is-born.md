# 0009 — How does a new skill get written?

**Status:** settled 2026-09-19  ·  **Commits:** dad6277 (the model skill)
**The model to copy:** `.claude/skills/fit-to-length/SKILL.md`

## The question
Jacek, on 2026-09-19, after cutting German Forgotten Bauhaus Hope to a
Short: "I want this skill to be a precedent for new skills that will
grow around the project." Skills will multiply. This record says what
makes a good one, so they stay alike and stay short.

## The answer: a skill is written *after* the job was done once, for real

`fit-to-length` was not designed up front. The job came first: 281.8 s
cut to 171.6 s, 8 cuts, no word split, the user saying "go" before
anything was edited. The skill came after, and it is a record of the
steps that worked, with the numbers they produced. Every new skill is
made the same way:

1. **Do the job once, by hand, in a session**, with the user watching.
   Don't write a skill for a job nobody has done yet.
2. **Write the skill the same day**, while the numbers are still at hand.

## What every skill has (copy fit-to-length's shape)

| Part | What goes in it | In fit-to-length |
|---|---|---|
| `description:` | what it does, **the words the user actually says** that should trigger it, and what it never does | "make it a Short", "get it under 3 minutes"; "never by speeding up or splitting words" |
| Opening paragraph | why the machine alone can't do this: the line between code and judgement | `--target` never cuts speech, and in a narrated film speech is the length |
| "Done first on …" | the real case: which film, which date, the before and after numbers | 281.8 s → 171.6 s in 8 cuts |
| Numbered steps | **try the machine first**, measure, propose, **wait for "go"**, commit before editing, edit, `film check`, peek | steps 1–8 |
| Measured numbers inline | thresholds and commands that worked, and what they gave | `silencedetect=noise=-38dB:d=0.2`; −58.7 dB silence against −25.6 dB speech |
| `## Never` | the tempting shortcuts that would betray the user | speed changes, invented `words:`, cutting mid-sentence |
| One row in root `CLAUDE.md` | skill name and when to use it, in the user's words | `"make it a Short"… — cut what is said twice` |

## Rules that come with it

- **The machine first, judgement second.** A skill starts from the
  command that already exists, and says where that command stops.
- **Propose before a destructive edit.** Anything that removes the
  user's words, shots or takes is shown as a table (what, seconds, why)
  and waits for a clear "go".
- **Say what was measured and what was reasoned**, in the proposal as
  everywhere else (0005).
- **Under ~100 lines.** The body loads only when the skill is used, but
  a long skill is a skill nobody checks. The detail belongs in decision
  records and docstrings; link to them.
- **If a step keeps needing judgement and could become a rule, it
  becomes code** (`change-the-machine`, a test first). The skill then
  gets shorter. Example: the word budget in the recording window
  (docs/plans/2026-09-20, item 7) moves "is it under 3 minutes?" from
  the end of the job to before recording.

## Where it is written down
`docs/HOW_CLAUDE_IS_SET_UP.md`, "Growing a new skill", points here.
