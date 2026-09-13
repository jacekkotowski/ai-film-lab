---
name: change-the-machine
description: Make a change to the ffilm/ package itself — a bug fix, a new command, a new rule — the way this repo does it — a test named as a sentence first, the smallest change that passes it, the whole suite, a commit that explains why. Use only after the user has explicitly asked for a code change.
---

# Change the machine: a rule, a test, a fix, a commit

Rules for this role: `ffilm/CLAUDE.md`. Read its "standing requests" and
"the layers" before planning anything.

## Steps

1. **Confirm the request is for code.** If the note is really about one
   film ("shot 4 is too long"), it is an `edit-pass`, not this skill.

2. **Commit or stash first**, so that `git diff` afterwards shows only this
   change. If the tree has changes you didn't make, ask about them; don't
   sweep them into your commit.

3. **State the rule in one sentence**, the way the user would say it.
   "A caption stops where the next one starts." That sentence becomes the
   test name and the commit title. (See `git log --oneline` — that is
   the house style.)

4. **Write the failing test first**, in `tests/`, testing a pure function.
   Run it and see it fail for the right reason:
   ```
   uv run --extra dev pytest tests/test_THE_RULE.py
   ```
   *Why:* a test you never saw fail may not test anything.

5. **Make the smallest change that passes it.**
   - Put new logic in a module, never in `cli.py`.
   - Imports only point down (the layer test says where a new module goes).
     No new dependencies.
   - A comment explains *why*, in the same plain voice as the docstrings
     around it: what broke, and what it looked like to the user.

6. **Run the whole suite.** `uv run --extra dev pytest`. All green, or say
   exactly what is red and why.

7. **If it changes what a film looks or sounds like, show it.** Render a
   `peek` or `draft` of a real project and say what to look for.

8. **Commit.** The title is the sentence from step 3; the body is what was
   wrong, how it was measured, and what changed.

9. **Record the decision** in `docs/decisions/` if a future session might
   be tempted to undo it.

## Done when

The new test failed before the change and passes after it, the full suite
is green, and the commit message would let a stranger understand why.
