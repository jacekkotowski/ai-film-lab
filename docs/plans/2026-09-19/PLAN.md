# Plan, 2026-09-19: narrate while looking at the picture

Written by Claude (Opus 5) on 2026-09-18, after Jacek asked: "I should
see the picture I am describing, press a button, go to the next
picture, describe it. Maybe text separated per picture?"

Rules as before: `change-the-machine`, test first, whole suite green,
one item per commit, measure before claiming. Never `film final`. The
acceptance is Jacek narrating `test_story` for real, nothing else.

## What exists and what does not

| Jacek wants | today | where |
|---|---|---|
| text separated per picture | **exists.** A blank line in `script.txt` starts a new paragraph, one paragraph is one slide, `[3]` on a paragraph's first line names its picture | `voice.script_paragraphs`, built 2026-09-17 |
| see the picture while talking | **missing.** `record --voice` opens the booth with no camera, so its self-view panel is a black rectangle. The booth is never told which photographs exist | `booth.session`, the `view` label |
| a button for "next picture" | **missing.** The prompter scrolls the whole script as one text. SPACE stops the take | `booth.session`, `on_space` |
| the film cut where he pressed next | **missing.** Cuts come from the script's paragraphs, or are guessed from pauses | `scaffold.cut_into_slides`, `scaffold.slide_cuts` |

What works today, as a stopgap: write `script.txt` with a blank line
between paragraphs, `uv run film record --voice`, then
`uv run film go --rewrite`. Each paragraph lands on its picture. He just
cannot see the picture while he talks.

## The mechanism

**One continuous take, with cues.** Pressing Next does not stop and
start a recording. It notes the moment. The take stays one wav, which
is what the voicing and the slides already expect; the cues are simply
the cut list `init` has so far had to guess.

    booth:  picture 1 + paragraph 1  --Next-->  picture 2 + paragraph 2  --Next-->  ...  --Finish-->
    saved:  media/voiceover_20260919-101500.wav
            media/voiceover_20260919-101500.cues.json   [0.0, 17.9, 38.6]
    init:   slide 1 = 0.0-17.9, slide 2 = 17.9-38.6, slide 3 = 38.6-end
            each cut moved to the nearest pause, so no word is split

The cue times are anchored on the END of the take, not the start:
`cue_in_wav = wav_length - (stop_time - press_time)`. Reasoned from
the code, not measured: in voice mode no camera frame ever arrives, so
the booth's clock starts on its 3-second fallback
(`got_frame or time.time() - S["t0"] > 3.0`), while the microphone is
already recording. Counting from the start would put every cut about
3 s early. Counting back from the end removes the start-up delay
whatever it is. Item 1 measures it.

**Precedence:** cues beat script paragraphs, and paragraphs beat
pauses. Pressing Next is the most direct statement of where a picture
changes. `caption --apply` still captions a cued film but no longer
re-cuts it.

## Items, in order

### 1. Measure before building (needs Jacek, 5 minutes)
Two things nobody has tested:
- Does `record --voice` open the booth cleanly with no camera? Open
  since 2026-09-17.
- How late the booth clock starts in voice mode. Jacek records 20 s:
  silent 3 s, says "one", silent 3 s, "two", presses SPACE. Compare the
  wall-clock start against the wav's first word from
  `ingest.detect_sound`. Numbers, not listening.

If the offset is near zero, anchoring on the end is still kept: it
costs nothing and cannot drift.

### 2. One rule pairs pictures with paragraphs
Pull the picture assignment out of `scaffold.slide_cuts` into a pure
`scaffold.picture_order(pictures, paragraphs) -> list[(picture, text)]`:
numbered order, `[3]` tags, the last picture reused when paragraphs run
over. The booth needs exactly that list, and one rule must decide it for
both. The booth is on the same layer as scaffold and cannot import it,
so `cli.cmd_record` builds the list and hands it to `booth.session`.

### 3. Cue times on the take's own clock
Pure `booth.cues_on_take(presses, stopped_at, take_seconds) -> list`.
Tests: anchored on the end; a press in the last half second is dropped;
times always rising and inside the take.

### 4. The booth shows the picture and the words for it
Voice mode only. The top of the record screen shows picture N large
and paragraph N beside it, or "picture 2 of 3" with no script. SPACE
or the Next button goes to the next picture; on the last one the
button reads Finish and ends the take. A Stop button stays for
abandoning a take. The cues are written beside the wav. When a take is
discarded, its cues file goes to `_discarded/` with it.

The window cannot be tested, so the choices in it are pure functions:
which picture and text to show for press count N, and the button's
label. Jacek tests the window itself.

### 5. `init` cuts where he pressed Next
Pure `scaffold.cut_at_cues(cues, first, last, pauses) -> pieces`. Each
cue moves to the middle of the nearest pause within 1.5 s. That number
is reasoned, not measured: people press a little after they finish a
sentence. With no pause that close, the cue is used as pressed. The
film's footer says the cuts are "where you pressed Next".

### 6. `caption --apply` keeps the cues
With a cues file, `caption` places captions and does not call
`slide_cuts`. Test on a fake film.

### 7. Acceptance on test_story, by Jacek
Jacek records a new narration of the three pictures in the booth,
pressing Next between them. Then `uv run film go --rewrite -p test_story`.
Measured:

| check | expected |
|---|---|
| booth opens with no camera | yes |
| each slide starts | within 0.5 s of where Next was pressed, inside a pause |
| no word split at a cut | transcribe the draft back; nothing missing |
| captions | on the slide whose picture was on screen when they were said |
| cues file | beside the wav; moved to `_discarded/` with a redone take |

## Not in this plan
Going back to a previous picture mid-take (redo the whole take instead;
three pictures is under a minute); re-recording one picture on its own;
anything in the sound chain; a video clip among the pictures.
