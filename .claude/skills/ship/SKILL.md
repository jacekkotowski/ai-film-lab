---
name: ship
description: Render the final, full-quality film and its thumbnail. Only when the user explicitly asks for the final render.
disable-model-invocation: true
argument-hint: "[project name]"
---

# Ship: the final render

`final` is the slow one: full resolution, original media, 4 motion
sub-frames. This skill can only be started by the user typing `/ship`.
Claude cannot pick it by itself, because `disable-model-invocation: true`
is set above. *Why:* a render the user didn't ask for costs them minutes
and tells them nothing new.

## Steps

1. **Check that the edit is settled.**
   `git status -- "projects/NAME/film.yaml"`. If there are uncommitted
   changes the user hasn't watched in a peek or draft, say so and ask
   whether to render anyway.

2. **Check once more.** `uv run film check -p NAME`. Read the title,
   music and thumbnail lines aloud to the user. They are the three things
   nobody typed and nobody sees until the end.

3. **Render.** Run it in the background; it takes minutes.
   ```
   uv run film final -p NAME
   ```
   When it finishes, the command itself writes `out/cover.jpg` and
   `out/upload.txt` (the words to paste), then **opens the `out/` folder
   and the YouTube upload page** on the user's screen. If the user wants
   neither, add `--no-open`. It never uploads anything; the user does that.

4. **Report** the output path, the runtime, and any `Careful:` lines it
   printed; those are what YouTube would reject. If the user wants a
   different title on the cover:
   ```
   uv run film cover -p NAME --title "…"
   ```

## Done when

`out/final.mp4` exists and the user has its path and any warnings. Do not
upload or share it anywhere yourself.
