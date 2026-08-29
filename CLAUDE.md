# AI FILM LAB — working agreement

You are my editing assistant. I am a data scientist, not a software
engineer. I read code fine; I don't want to maintain much of it.

## The one rule

**Edit `film.yaml`. Do not edit `ffilm/` unless I explicitly ask.**

`film.yaml` is the film. `ffilm/` is the machine that renders it. When I
say "too fast", "too repetitive", "hold that one longer" — that is a
change to `film.yaml`, and almost always a change to a *number*. If you
find yourself editing `render.py` to fix a pacing note, you have
misunderstood the request.

The exception: `ffilm/moves.py` holds the taste constants (`PUSH`, `PAN`,
`DRIFT`, `ROLL`, `SETTLE`, `BASE`). If a note applies to the *whole film*
rather than one shot, changing one of those is correct. Say so when you do.

## Workflow

**Step A — analyse.** `uv run film ingest` reads `media/` and writes
`analysis/`. Then `uv run film init` writes a first `film.yaml`. You may
run both yourself. Treat `init` output as a rough draft to improve, not
as something you authored.

**Step B — understand the material.** I show you
`analysis/contact.jpg` and tell you what the film is about. Read
`analysis/manifest.json` for the detected focus points and, for video,
`analysis/cuts/`.

**Step C — write the edit.** You rewrite `film.yaml`: ordering, durations,
moves, captions. Run `uv run film check` afterwards, always.

If you did have to touch `ffilm/`, run the tests too — they are fast and
they exist because every rule in them broke in front of me once:

    uv run --extra dev pytest

**Step D — I look.** `uv run film peek` for order and pacing (seconds),
`uv run film draft` for motion (under a minute). You can run these
yourself and tell me when they are ready.

**Step E — I react.** I tell you what feels wrong in plain language. You
make small edits to `film.yaml`. **Return to Step D.** This loop is the
whole system; expect to go round it many times.

**Step F — ship.** `uv run film final`, only when I ask. It is the slow one.

I may also be editing `film.yaml` in the browser bench
(`uv run film edit`) or in Notepad++ while you work. If the file may have
changed since you last read it, re-read it before editing. The bench
rewrites the file, so `#` comments do not survive — put anything that
must persist in a `note:` field.

## Editing principles

- **Change few things at a time.** If I give three notes, make three
  small edits, not one rewrite. I need to see which change did what.
- **Commit before big changes.** `git add -A && git commit -m "..."`.
  If an edit makes things worse, I want `git diff` to show me why.
- **Preserve my hand-tuned shots.** If a shot has explicit `from:`/`to:`
  windows, I put them there deliberately. Don't replace them with a
  named move.
- **Use `note:` fields.** They're never rendered. Write down *why* a shot
  is 7 seconds. Future-me and future-you both need that.
- **Never touch `media/`.** Originals are read-only, always.

## Taste defaults (argue with me, but start here)

- No two consecutive shots use moves from the same family. `choose_moves()`
  enforces this for `move: auto`; respect it when choosing by hand.
- Most shots should be `drift_*` or `static`. Big moves are punctuation —
  if everything pushes in, nothing does.
- A `static` shot before an emotional one makes the emotional one land.
- Captions stress, they don't narrate. If the caption says what the
  picture already says, cut it.
- Shots with faces get longer duration than shots without.
- Total caption time under ~20% of runtime.

## Video shots

- `in`/`out` are timecodes into the source. `analysis/cuts/<name>.json`
  has detected shot boundaries — use them as candidate in/out points.
- Video can move too: `punch_in` on a video shot is a reframe, and it's
  how you make one clip yield two different shots.
- `peek` and `draft` use 480p proxies automatically. `final` uses the
  originals. Never point `film.yaml` at a proxy by hand.

## Things not to do

- Don't add dependencies. The whole point is four packages.
- Don't add features I haven't asked for. If you think something's
  missing, say so in one sentence and wait.
- Don't add transitions, effects, or "polish" unprompted. Cuts are fine.
  Cuts are almost always fine.
- Don't render `final` unless I ask. It's the slow one.

## Where things are

```
THE SPINE -- read these first, in this order
  ffilm/spec.py       what a film IS. Every other file exists to turn
                      these objects into pixels.
  ffilm/scaffold.py   media -> a first film.yaml. All the editing
                      decisions live here: what to keep, how long,
                      what order, where the dead air goes.
  ffilm/render.py     film.yaml -> pixels. The camera is one function
                      (`warp`), twelve lines long.
  ffilm/moves.py      the movement vocabulary + the taste constants

GETTING THE MATERIAL
  ffilm/record.py     camera + mic -> a file in media/. Windows/dshow.
                      Devices are discovered, never hardcoded, and the
                      choice is remembered per MACHINE in .devices.json
  ffilm/booth.py      the one window: paste your words, record, again,
                      done. Self-view, sound level, teleprompter. Fed by
                      the SAME ffmpeg that writes the file -- dshow will
                      not give one webcam to two programs, and the
                      picture is SPLIT, never mapped twice (see the
                      comment there; mapping twice starves the file)

LOOKING AT THE MATERIAL
  ffilm/ingest.py     media -> contact sheet, manifest, proxies, where
                      the sound and the pauses are
  ffilm/kinds.py      what counts as a photo, a clip, a track. One list.

SOUND AND WORDS
  ffilm/audio.py      speech + narration + music -> one track. Ducking,
                      loudness, the joins.
  ffilm/voice.py      speech -> timed lines (optional: --extra voice)
  ffilm/caption_fit.py  which line belongs on which shot
  ffilm/cover.py      the YouTube thumbnail. NOT part of the film --
                      it has no shot and no duration, which is exactly
                      why it lives in its own folder
  ffilm/library.py    the shelf: the music and the two cover pictures
                      that EVERY film uses. Filled in once. A project's
                      own music/ or cover/ folder always wins.
                      FFILM_LIBRARY moves it or switches it off

THE WAY IN
  ffilm/cli.py        the commands. Mostly argument parsing + dispatch.
  ffilm/guide.py      `uv run film` -- what do I do next? Also what
                      FILM.bat runs.
  ffilm/editor.py     the browser bench (`film edit`)
  ffilm/history.py    every render commits film.yaml, so there is an undo

  ffilm/data_clip.py  CSV -> an animated clip, for the RStudio side
  blender/            the 3D backend, for parallax later

tests/                pure functions only, runs in under a second:
                        uv run --extra dev pytest

library/          shared by every film. Filled in once, not per project
  music/          one background track for all of them
  cover/          two thumbnail backdrops: one wide, one tall. The film
                  takes whichever is its shape and prints its title on
                  it -- as the thumbnail AND as the opening 4 seconds
                  (scaffold.TITLE_CARD_SECONDS, written into film.yaml
                  as shot s00, pointing at analysis/title.jpg)

projects/<name>/
  media/          originals. READ ONLY.
  music/          one background track -- overrides library/music/
  cover/          this film's own thumbnail picture -- overrides
                  library/cover/, and its filename becomes the title.
                  Scanned by NOTHING -- put one here, not in media/,
                  or it becomes a shot in the film
  script.txt      what `film record` scrolls at you while you talk.
                  You do not have to make it -- the record window saves
                  whatever you paste into it here. Hard line breaks are
                  re-flowed; blank lines are kept as paragraph gaps
  analysis/       contact.jpg, manifest.json, proxies/, cuts/
  film.yaml       THE FILM
  out/            renders, and cover.jpg
```
