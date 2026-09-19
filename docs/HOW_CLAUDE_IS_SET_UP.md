# How Claude is set up in this repo

This repo is also a worked example of **programming with an AI assistant**.
This page explains the set-up: what each piece is, when Claude reads it,
and how to decide where a new piece of knowledge belongs.

Nothing here is specific to films. Copy the shape.

---

## The idea in one picture

An instruction can be *said*, or it can be *made true*. The further down
this ladder a rule sits, the less it depends on the model remembering it:

```
  said          CLAUDE.md             "Edit film.yaml, not ffilm/"
    │           nested CLAUDE.md      "Faces hold longer than landscapes"
    │           skills                "An edit pass goes: re-read, split notes, …"
    │           decision records      "Parallel rendering: measured, worthless"
    │           tests                 "A caption stops where the next one starts"
    ▼           hooks                 "media/ cannot be written. Full stop."
  made true
```

**The rule of thumb:** begin a rule as a sentence. If it ever gets broken,
move it one step down.

- A mistake that recurs goes into a skill.
- A mistake that must never happen again becomes a test or a hook.

"Never touch the originals" began in CLAUDE.md. It is now a hook, because
"almost always" isn't good enough for someone's only copy of their
photographs.

---

## The pieces

| Piece | File(s) | When Claude reads it | What belongs there |
|---|---|---|---|
| **Root agreement** | `CLAUDE.md` | every session, always | who you are being, the one rule, pointers. Keep it short: it costs context on every turn |
| **Nested rulebooks** | `projects/CLAUDE.md`, `ffilm/CLAUDE.md` | only when Claude works in that folder | rules for one *role*: editor or developer |
| **Skills** | `.claude/skills/*/SKILL.md` | the one-line `description` always; the body only when the skill is used | a *procedure*: numbered steps, a why for each, a "done when" |
| **Hooks** | `.claude/settings.json` + `.claude/hooks/*.py` | never read, **executed** on events | anything that must happen every time, or must never happen |
| **Permissions** | `.claude/settings.json` → `permissions` | enforced by Claude Code | which commands run without asking |
| **Decision records** | `docs/decisions/` | when a rulebook or skill points there | a question that cost real time, the numbers, the answer |
| **Docstrings** | top of each `ffilm/*.py` | when Claude opens that file | what the module *is* and why it is shaped that way |
| **Tests** | `tests/test_<a sentence>.py` | when run | a behaviour that broke once and must not break again |
| **Personal memory** | `~/.claude/projects/…/memory/` | by that user's Claude only | facts about *one person or one machine*. Not shared, so not project knowledge |

### Why skills are per *workflow*, not per *module*

The tempting design is one skill per file: an `audio` skill, a `render`
skill. That duplicates the docstrings, and the two drift apart.

A skill answers "**how do I do this job**", and the jobs here cut across
modules: making a first cut touches `ingest`, `scaffold`, `moves` and
`render`. What a module *is* belongs in its docstring, next to the code
it describes.

| Skill | The job | Who starts it |
|---|---|---|
| `new-film` | media → first peek | Claude or `/new-film` |
| `edit-pass` | notes → small edits → render | Claude or `/edit-pass` |
| `investigate` | measure a fault before explaining it | Claude or `/investigate` |
| `change-the-machine` | test first, then code, then commit | Claude or `/change-the-machine` |
| `ship` | the slow final render | **only** `/ship` (`disable-model-invocation: true`) |
| `fit-to-length` | cut a film to a length (a Short: 3:00) by dropping what is said twice | Claude or `/fit-to-length` |

### Growing a new skill

Skills will multiply as the project grows. **`fit-to-length` is the
model to copy**, and `docs/decisions/0009-how-a-skill-is-born.md` says
why. In short:

1. Do the job once, for real, in a session.
2. Write the skill the same day, with that case's numbers in it.
3. Give it the same parts:
   - a `description` holding the user's own trigger words;
   - "why the machine alone can't";
   - "done first on…";
   - numbered steps: machine first → measure → propose → wait for "go" → edit → check → peek;
   - a `## Never` list;
   - one row in root `CLAUDE.md`.

### Why two rulebooks

The same person asks for two different kinds of work:

- **Editor**: "shot 3 drags". The right answer changes a number in a YAML file.
- **Developer**: "the render is slow". The right answer may change Python.

The most common failure was answering an editor request as a developer:
rewriting `render.py` to fix a pacing note. Separate rulebooks, loaded by
folder, keep each role's context small and its rules sharp.

---

## Where does a new piece of knowledge go?

```
Is it about ONE person or ONE machine?          → personal memory
Must it happen EVERY time, with no exceptions?  → hook
Did it break once, and is it checkable in code? → test
Is it "we tried X, here are the numbers"?       → docs/decisions/
Is it a sequence of steps for a recurring job?  → skill
Does it apply to one role or one folder?        → nested CLAUDE.md
Does every session need it, whatever the task?  → root CLAUDE.md  (rarely)
Is it what a module is or does?                 → that module's docstring
```

---

## Trying it

- **Type `/`** in Claude Code to see the skills; `/ship` starts the final render.
- **See the guard work:** ask Claude to "write a note into
  `projects/<film>/media/`". It will be refused, with the reason.
- **See the check work:** ask for any edit to a `film.yaml`. The
  `film check` output arrives with the edit.
- **Test a hook by hand.** They are plain Python reading JSON from stdin:
  ```powershell
  echo '{"tool_input":{"file_path":"projects/x/media/a.jpg"}}' | python .claude/hooks/guard_media.py
  ```
- **Switch hooks off** for a session: `/hooks` in an interactive `claude` terminal.

---

## What this set-up deliberately does not have

- **No framework.** No agents calling agents, no MCP servers, no vector
  database. Plain files that a person reads the same way Claude does.
- **No duplicated knowledge.** Each fact has one home, and the other
  places point to it. A map copied into three files is wrong in two of them
  within a month.
- **No rule without a reason.** Every rule says *why*. A model, like a
  new colleague, applies a rule well only when it knows what the rule
  protects.
