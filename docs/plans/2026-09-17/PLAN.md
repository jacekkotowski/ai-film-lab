# Plan for 2026-09-17: photos and clips together, and a voice over them

Written by Claude (Fable 5.1) on the evening of 2026-09-16, after
yesterday's plan was executed (`docs/plans/2026-09-16/PLAN.md`). Same
rules: the `change-the-machine` skill, a test named as a sentence first,
one item per commit, measure before claiming. **P** is the producer,
**D** the developer.

## What is true tonight

**Measured.** Every one of the 16 projects on this machine is one
talking clip: no photographs, no separate audio, no AI-made intro. So
the photo path, the mixed path and the voiceover path have never been
exercised on a real film, only in the unit tests.

**Measured, tonight, on a scratch project** (`mixed_project.py`: three
photos, a 12 s clip with speech, a 14 s `voiceover.wav`): `ingest`,
`init`, `check`, `caption` and `peek` all ran without an error. So the
chain is not broken. What it does is the question:

| what happened | where | verdict |
|---|---|---|
| `init` found `voiceover.wav`, wrote `audio:` and `audio_offset: 0.0` | scaffold.build | works as documented |
| the narration starts at 0.0, under the 4 s title card | `audio_offset` | wrong default: the card is silent by design |
| photos got 4.5 s (5.5 s with a face), the narration's sentences are longer; `caption` said "cut short, the shot ends first" | scaffold STILL_SECONDS, caption_fit | the photos do not know about the narration |
| the film is 27.4 s; the narration is 14 s and the clip's own speech runs from 18 s | audio.build_soundtrack | fine here; see the next row |
| a narration LONGER than the pictures is cut at the film's end by `apad,atrim=0:total` (audio.py, the last filter) with **no message** | audio.build_soundtrack | the failure mode to design against |
| the note in render.py about "the voiceover is shorter than the video" cannot fire any more: sound is a second pass, `stopped_early` no longer happens for audio | render.render | dead text; misleading |
| both the narration and the clip's own talking are mixed, at the same level | audio | right for B-roll with room sound; wrong if you talk in both |
| `ingest` ignores the .wav ("not photos or clips") and says so | ingest | correct |

**Read, not run.** `film record` already supports a microphone with no
camera (`record_command(video=None, ...)` maps `0:a`), and `cmd_record`
prints `Camera: (none)`. Whether the recording window (`booth.py`)
opens with no picture is **not verified**. A mic-only take would be
named `rec_*.mp4` by `take_name`, which `ingest` would then try to read
as a clip. `voice_sources` matches the name `voiceover.` exactly, so
`voiceover_20260917.wav` would fall to "any standalone audio" and print
the note about music.

## The shape of it, so nothing explodes

Nothing new is invented. A voiceover is already a thing the film knows
(`audio:`), the recording window already exists, the pause finder
already exists, `fit_to_target` already scales photographs. Tomorrow
connects them, in the places a user already looks:

- The walk-through gets **one** new alternative, in the slot where
  "say it to the camera" already sits: *"...or say the words over these
  pictures"*, offered when a film has photographs and no narration.
- `film record` gets **one** flag, `--voice`, meaning microphone only.
  Same window, same scrolling script, same ENTER and SPACE.
- `film init` does what it already does, with the narration's length
  and pauses as one more input.
- No new module. No new film.yaml field. No new dependency.

## Items, in order

### 1. Two failure modes said out loud (smallest, first)

- **A narration longer than the pictures.** `checks.py`: when
  `film.audio` is set, compare its length (`audio._dur`) to
  `film.duration`; `film check` and the render say
  `-- 41 s of narration under a 27 s film: the last 14 s will not be
  heard. Hold the photographs longer, or film go --target 41`.
  Pure `narration_note(audio_seconds, film_seconds) -> str | None`,
  test `test_a_narration_longer_than_the_film_is_said_before_the_render`.
- **Delete the dead note in `render.render`** about the voiceover being
  shorter, and its `stopped_early and film.audio` branch. Test: none
  needed; the suite stays green.

**P:** silence at the end of what you recorded, with no word about it,
is the worst outcome on the list. **D:** two functions, one deletion.

### 2. The narration starts after the title card

`scaffold.build` writes `audio_offset: 0.0`. When it also writes the
title card block, write `audio_offset: <card seconds>` instead, with a
comment: `# the narration waits for the opening card`. Pure: `build`
is already testable (`tests/test_title_card.py` reads its output).
Test `test_the_narration_waits_for_the_opening_card`. One line.

### 3. Photographs follow the narration

This is the item that makes a voiceover film watchable, and it is the
inverse of something already built. `scaffold.fit_to_target` shortens
photographs to hit a target and never touches speech. Add the other
direction: when `audio:` is set and the narration is longer than the
pictures, **stretch the photographs** so the film covers the narration
(plus the card, plus `music_fade`). Same function, a target that can
be larger than the sum. Clips are never stretched.

Then the better cut, if there is time: cut the photographs **where the
narration pauses**. `ingest` already finds the pauses in a clip's sound
(`sound_of`, the `quiet` list, `QUIET_FRACTION`); run the same measure
on the voiceover file and give each photograph the stretch between two
pauses. Pure `photo_durations(pauses, n_photos, total) -> list[float]`,
test `test_each_photograph_holds_for_one_breath_of_narration`. Keep
FACE_SECONDS as a floor, not a rule.

**P:** a picture that changes on the breath is what an edited film
does; a picture that changes at 4.5 s regardless is a slideshow. **D:**
the first half is ten lines in a function that exists; the second half
is one pure function and one call. Do the first half before the second.

### 4. Record a voiceover from the same window

- `record.take_name(audio_only=True)` -> `voiceover_YYYYmmdd-HHMMSS.wav`
  (`REC_PREFIX` stays for takes with a picture). Test
  `test_a_microphone_only_take_is_a_voiceover_not_a_clip`.
- `voice.voice_sources`: match `voiceover` as a prefix, not
  `voiceover.` exactly. Test
  `test_a_dated_voiceover_is_still_the_narration`.
- `cli.cmd_record --voice`: choose no camera, and say so. **Verify by
  running it once** that the booth window opens with no picture; if it
  does not, run it `--headless` (the flag exists) with the level meter
  in the terminal, and say that in the plan rather than build a window.
- `guide._get_material` is the wrong place: it is for an empty project.
  Add the step in `next_steps` where the film has photographs, no clip
  with sound, and no `audio:`: *"...or say the words over these
  pictures"* -> `record --voice`. After the take, the guide's next step
  is `init` again (the manifest is not older than the media, so today it
  would offer `peek`; the check for "narration newer than film.yaml"
  is one `_mtime` comparison). Tests in `test_guide.py`, which already
  builds fake projects.

**P:** this is the whole feature from the user's chair: drop photos in,
press ENTER, talk, press ENTER. **D:** four small changes in four files
that already do most of it.

### 5. The other material, tested as material

Run `mixed_project.py` again with two more files added by hand and
look at the result, not the log:

- an **AI-made intro clip with no speech** (any short mp4 with music
  only): it should be sampled as B-roll, and its sound should not be
  in the mix at the narration's level. Today `keep_clip_audio` mixes
  every clip's sound. Decide, and write it down: a clip with no speech
  in it (ingest's `ratio` under the pause finder's threshold) plays
  under the narration at music level, or is muted. Producer's call;
  D's guess is muted, since its music would fight the library's.
- a **.HEIC photograph** off a phone (there is none on this machine;
  ask Jacek for one or skip and say so).
- a **vertical film** of the same folder (`film new ... ` then
  `film shape --vertical`): photographs crop around their focus point,
  and the wide clip gets `framing_notes`.

Acceptance is a peek Jacek watches, not a number. Write what was seen
into this file.

### 6. Not touched tomorrow

The voice chain (0003, 0008), the music bed (0007), the look, captions
from the clips' own talking, `scaffold`'s ordering rules, and the bench.
If item 3's second half is not done by the end of the day, it waits.

## What "not exploding" means here

- Every item is a change to a function that exists, in a file that
  exists, tested the way that file is already tested.
- The user sees one new line in the walk-through and one new flag.
- A film made before tomorrow renders exactly as it did, because
  nothing changes unless `audio:` is set or `--voice` is typed.
- The scratch project is the test bed; no real project is edited.
