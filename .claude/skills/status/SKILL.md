---
name: status
description: Say where a film stands in one screen — what is recorded, whether the edit fits its length, which renders are current and which are stale, what could be uploaded by mistake, and the ONE next step. Read-only. Use when the user says "where am I", "what's left", "is it ready", "status", "can I upload it", or comes back to a film after a break.
---

# Status: one screen, one next step

The guide (`uv run film`) answers "what next?" from file times, and its
"So far" line says what is recorded. It does not say **what on disk is
out of date**, and that is what hurts a producer in a hurry: an old
`final.mp4` looks exactly like a new one.

Done first on 2026-09-19, German Forgotten Bauhaus Hope, after it had
been cut to a Short. The guide said "watch the draft". The status also
found:
- `final.mp4` was the old 281.8 s cut, not the 171.6 s Short;
- `upload.txt` still listed the sentences that had been cut;
- `narration.txt` was not in git, so its only copy was on disk.

## Steps (read only — change nothing)

1. **Recorded.** Print the guide's own line, so the words match what the
   user sees in `uv run film`:
   `guide.so_far([f.name for f in (project/'media').iterdir() if f.is_file()])`.
   Add which pictures carry words: the `voice:` shots in `film.yaml`.

2. **Edit.** Run `uv run film check -p NAME` and take:
   - the `OK` line (shots, seconds);
   - the `!!` lines;
   - media in no shot.

   Compare the length with the target: a Short is ≤ 180 s.

3. **Renders, current or stale.** For `peek`, `draft`, `final`,
   `upload.txt` and `cover.jpg` in `out/`:
   - a file is **stale** if it is older than `film.yaml`;
   - also measure each render's length with `ffprobe`. A stale final
     with a different length than the edit is the dangerous one, so say
     it in bold.

4. **Open questions.** Anything decided but not yet seen at the right
   quality (a look judged only in the 360p peek). Suspect captions: the
   `fix-captions` rule, under 1.2 s on screen.

5. **Safety.** Run `git status --short -- projects/NAME`. Name any text
   the user wrote that is untracked: `narration.txt`, `script.txt`.
   `media/` and `out/` are ignored on purpose; don't flag them.

6. **The one next step.** One command, and why. Usually the cheapest
   render that is stale: peek → draft → final. `final` only as a
   suggestion; it runs only when the user asks (the `ship` rule).

## Output shape

Six bullets at most, headed "NAME: status, DATE TIME":
- recorded
- edit
- renders
- open
- safety
- next step

✓ or ✗ in front of each item.

## Never

- Change a file, render, or commit. Status is read only.
- Say "ready to upload" when the final is older than `film.yaml`.
- Report a length without measuring it.
