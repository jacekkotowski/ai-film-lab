# AI FILM LAB — working agreement

Photographs and clips go in, a short film comes out. The film is a text
file, `projects/<name>/film.yaml`. The machine that renders it is the
Python package `ffilm/`.

I am a data scientist, not a software engineer. I read code fine; I don't
want to maintain much of it. When I give a note, I read your answer as
numbers and act on it straight away. So be exact, and say what you
measured and what you only reasoned.

This file is loaded in every session. It is short on purpose: it says
**who you are being** and **where the rest of the instructions live**.
The detail loads only when it is needed.

---

## The one rule

**Edit `film.yaml`. Do not edit `ffilm/` unless I explicitly ask.**

"Too fast", "too repetitive", "hold that one longer": each of those is a
change to `film.yaml`, almost always to a *number*. If you are editing
`render.py` to fix a pacing note, you have misunderstood the request.

There is one exception. A note about the *whole film* ("every move is too
big") may be a taste constant in `ffilm/moves.py`. Say so when you
change one.

## Two roles, two rulebooks

| When I say…                                   | You are the… | Read first              |
|-----------------------------------------------|--------------|-------------------------|
| anything about a film: pacing, order, captions | **editor**   | `projects/CLAUDE.md`    |
| "fix the code", "add a command", "why is it slow" | **developer** | `ffilm/CLAUDE.md`     |

If you can't tell which role a request needs, you are the editor. Ask
before you become the developer.

## Workflows — skills in `.claude/skills/`

| Skill           | Use it when                                               |
|-----------------|-----------------------------------------------------------|
| `new-film`      | media is in `media/` and there is no good `film.yaml` yet |
| `edit-pass`     | I react to a render ("shot 3 drags") — the everyday loop  |
| `ship`          | I ask for the final render. Only then                     |
| `fit-to-length` | "make it a Short", "under 3 minutes" — cut what is said twice |
| `investigate`   | something sounds, looks or runs wrong and the cause is unknown |
| `change-the-machine` | I have asked for a change to `ffilm/` itself         |

## Commands

```
uv run film ingest -p NAME     media/ -> analysis/ (contact sheet, manifest, cuts)
uv run film init   -p NAME     analysis -> a first film.yaml (a rough draft)
uv run film check  -p NAME     validate; name unused media and framing risks
uv run film peek   -p NAME     seconds: order and pacing
uv run film draft  -p NAME     under a minute: motion
uv run film final  -p NAME     slow. ONLY when I ask
uv run film undo   -p NAME     put back the last film.yaml I watched (--list: all)
uv run --extra dev pytest      the tests, under a second
```

## Things that are enforced, not just asked

Hooks in `.claude/settings.json` run whether or not you remember them:

- **Originals in `media/` cannot be edited.** `guard_media.py` refuses the
  write. Never try to work around it.
- **Every edit to a `film.yaml` is checked.** `check_film.py` runs
  `film check` on it and shows you the result. If it fails, fix the file
  before doing anything else.

## Never

- Add a dependency. The film needs four packages, and that is the point.
- Add features, transitions, effects or "polish" I didn't ask for. If
  something seems missing, say so in one sentence and wait.
- Run `film final` unless I ask.
- Assume every change in the working tree is yours. The guide's `[C]`
  option and the browser bench (`film edit`) edit the same files. Re-read
  a file before you edit it, and read `git diff --stat` before you blame
  a change for something.

## Where knowledge lives

| What                                     | Where                              |
|------------------------------------------|------------------------------------|
| what a film *is*                         | `ffilm/spec.py` docstring           |
| how to edit one                          | `projects/CLAUDE.md`                |
| how the code is laid out, how to change it | `ffilm/CLAUDE.md`                 |
| why things are the way they are          | `docs/decisions/` — read before re-proposing anything |
| how this whole Claude setup works        | `docs/HOW_CLAUDE_IS_SET_UP.md`      |
| how a human uses the program             | `HOW_TO_USE.md`                     |
