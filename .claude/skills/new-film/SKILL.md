---
name: new-film
description: Turn a project's media/ folder into a first watchable film.yaml — ingest, draft, look at the material, rewrite the draft, check, peek. Use when a project has footage but no film.yaml, or the user says "start", "make a first cut", "write the edit".
argument-hint: "[project name]"
---

# New film: from a folder of media to a first peek

The goal is a first cut the user can react to, not a finished film. Aim
for "clearly intentional, easy to criticise".

Rules for this role: `projects/CLAUDE.md`.

## Steps

1. **Find the project.** Use the name given, or `$ARGUMENTS`. If neither,
   list `projects/` and ask. Do not guess between two films.

2. **Analyse the media.**
   ```
   uv run film ingest -p NAME
   ```
   *Why:* everything after this reads `analysis/`, not `media/`. It is
   cached per file, so re-running it is cheap.

3. **Write the scaffold.**
   ```
   uv run film init -p NAME
   ```
   If a `film.yaml` already exists, **stop and ask.** `init --force`
   replaces it. *Why:* the existing file may hold hand-tuned work.

4. **Look before you edit.** Read `analysis/contact.jpg` (it is an image —
   look at it) and `analysis/manifest.json`. If `script.txt` exists, read it:
   it is what the film is *about*. If the user hasn't said what the film
   is about, ask once, in one sentence.

5. **Rewrite the draft. Treat `init` output as a draft, not as your own
   work.** In order:
   - **order**: an opening, a turn, an ending. Not the camera's file order.
   - **durations**: faces longer, and the emotional shot longest.
   - **moves**: mostly `drift_*`/`static`; no family twice in a row.
   - **captions**: stress, not narration; under ~20% of the runtime.
   - **`note:`** on any shot whose duration or move is a deliberate choice.

6. **Check.** The hook runs `film check` after every edit and shows you the
   result. Resolve what it reports: a broken file, media in no shot, a
   subject cropped by a tall frame. Leaving a file out on purpose is fine
   if you say so.

7. **Commit the first cut.**
   ```
   git add "projects/NAME/film.yaml" && git commit -m "NAME: first cut"
   ```

8. **Peek.**
   ```
   uv run film peek -p NAME
   ```
   Tell the user where the file is. Summarise the edit in at most five
   lines: how many shots, the runtime, and the one or two choices they
   should judge.

## Done when

`film check` is clean or its warnings are explained, the peek has
rendered, and the user has been told what to look at. Then stop. Their
reaction starts the `edit-pass` skill.
