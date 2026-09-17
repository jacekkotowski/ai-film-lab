# Plan B, 2026-09-17: a voiceover film that a person can edit

Written by Claude (Fable 5.1) after Jacek's own test, `projects/test_story`
(three vertical pictures, a 59.5 s narration recorded with
`film record --voice`, no script). The morning's run declared its items
done on a scratch project; this test is the acceptance it never had.
**Executed by Opus. Acceptance is `test_story`, nothing else.**

Rules as before: `change-the-machine`, test first, whole suite with the
exit code checked, one item per commit, measure before claiming. Never
`film final`; never edit `media/`; `film.yaml` of `test_story` may be
rewritten by `init --force` (it is the test), the old one is kept as
`.bak` and in git.

## What the test measured

| Jacek saw | measured cause | where |
|---|---|---|
| pictures out of order (3, 1, 2) | the order hint needs a separator after the number: `_NUM_PREFIX = ^(\d{1,3})[_.\-\s]+`. `3_declaration…` matched, `1declaration…` and `2declaration of love` did not, so the one numbered file went first and the rest followed alphabetically | `scaffold.py:99` |
| narration not captioned; `upload.txt` has no chapters | nothing ran `film caption`. The guide's path after a voiceover is `init --force` → peek → draft → final; captioning is a side option offered only at the "Ship it" stage. Run by hand as a preview it works: 12 lines, placed on the 3 slides by `fit_global`, one "cut short" | `guide.next_steps` |
| no way to say which picture goes with which words | `init` stretched the three pictures evenly (23.3 / 19.1 / 19.1 s) to cover 59.5 s. The narration has 16 speech stretches and 17 pauses ≥ 0.7 s; none of that reaches the pictures | `scaffold.fit_to_target` |
| `film.yaml` still says "Speech captions are left out on purpose" | the footer is written whenever there is no `quote_` file, narration or not | `scaffold.build` |

The claim in the film.yaml header that `00_ 01_` orders files is true and
was tested; the rule just did not accept `1name.png`. That is a wrong
rule, not a missing one.

## The mechanism: a slide is a shot with a piece of the narration

This is the same thing a talking take already is. A take is cut at its
pauses; each piece becomes a shot with `in:`/`out:` on the clip, the
soundtrack places each piece at its shot, captions are fitted per piece,
and you edit by moving, trimming or deleting shots in `film.yaml` or the
bench. A voiceover film gets exactly that, with the picture and the
sound coming from two files instead of one:

```yaml
  - id: s01
    src: media/1declaration_of_love.png
    voice: media/voiceover_20260917-105656.wav
    in: "00:02.05"          # this slide's words, on the narration's clock
    out: "00:18.20"
    move: drift_left
    note: "paragraph 1 of 3 -- 'I remember I was stressed…'"
```

- `duration` defaults to `(out - in) + VOICE_TAIL` (0.4 s of the picture
  after the last word). Set it longer to hold the picture; the words do
  not stretch.
- Reorder the shots and the narration reorders with them. Swap `src` to
  put a different picture under the same words. Delete a shot and its
  words go with it. `film undo` and the bench need no change: they
  already move whole shots.
- The film-wide `audio:` stays for whoever wants one continuous track
  under everything; `init` stops writing it when it writes slides with
  `voice:`.

### How the pieces are found

1. **With a script** (the normal case; the recording window scrolls it):
   **one paragraph = one slide.** `voice.align_to_script` already gives
   each written sentence its spoken times; group by paragraph, take the
   first word's start and the last word's end, and pad by the same
   breath `scaffold` uses when it cuts a take at a pause. Pictures are
   assigned to paragraphs in order (picture 1 → paragraph 1 …). A
   paragraph may name its picture on its first line, `[3]` or
   `[3_declaration_of_love.png]`, and then that picture is used; more
   paragraphs than pictures reuse the last picture; more pictures than
   paragraphs share the last paragraph. This needs the speech model, so
   it happens in `film caption --apply` (and in `go`, which runs it).
2. **Without a script** (Jacek's test): `init` splits the narration at
   its longest pauses into as many pieces as there are pictures. Pure,
   from the pause list `ingest` already computes for clips
   (`sound_of` / `QUIET_FRACTION`), run once on the narration file. On
   `test_story` the three longest pauses are 34.45–37.4, 7.7–9.55 and
   10.25–12.2 s; the split for three pictures is at 34.45 and either
   7.7 or 10.25. Write which into the note.
3. `film caption` without a script captions by listening, as now, and
   fits captions per slide through the `voice` source.

## Items, in order

### 1. A leading number orders a file, with or without a separator
`_NUM_PREFIX = ^(\d{1,3})(?=\D)`. Tests: `1declaration_of_love.png`,
`2declaration of love.png`, `3_declaration_of_love.png` come out 1, 2, 3;
`IMG_0042.jpg` and `20260917.jpg` are still unnumbered. Then
`init --force` on `test_story` and `film check` shows s01 = 1…, s02 = 2…,
s03 = 3….

### 2. `voice:` on a still shot (spec, sound, captions, check)
- `spec.Shot`: field `voice: str | None`; `in`/`out` parsed for stills
  when `voice` is set; `duration` default as above; `validate` says
  when the voice file is missing or `out ≤ in`.
- `audio.build_soundtrack`: the specs loop adds one entry per still with
  `voice` (src = the voice file, start = tin, end = tout, delay = the
  shot's frame position, speed 1.0). Everything after that (voice once
  per take, pieces cut from it, ducking, levels) is unchanged and is
  why this is small.
- `caption_fit.fit_per_clip` and `voice.voice_sources`: a shot's sound
  source is `s.voice or s.src`; a narration file used by slides is a
  per-clip source (its `shot_srcs` are those slides), not a global one.
- `checks`: the narration note from the morning (item 1 there) applies
  only to `audio:`; slides with `voice:` cannot run out.
Tests as sentences for each; the pure parts are the spec parsing, the
specs list (`build_soundtrack` has no pure half today: extract
`speech_specs(film, fps) -> list` and test that), and the fitting.

### 3. `init` cuts the narration at its pauses, one piece per picture
`scaffold.build`: with a narration and no script, measure its pauses
(reuse the clip pause finder on the wav), split into `len(pictures)`
pieces at the longest pauses, write one slide per picture with
`voice:`/`in:`/`out:`, notes saying which pause was cut at, no
`audio:`, no "captions left out" footer, and a footer line saying
`# 3 slides cut from a 59.5 s narration at its pauses; film caption
--apply with a script.txt re-cuts them by paragraph`. Test with a fake
pause list. Then `init --force` on `test_story` and `peek`.

### 4. `film caption --apply` re-cuts slides by script paragraph
In `cmd_caption` after transcription, when the film has slides with
`voice:` and `script.txt` has paragraphs: compute the paragraph windows
(pure `paragraph_windows(lines_aligned, paragraphs) -> list[(in, out)]`),
rewrite the slides' `in`/`out`/`src` through `scaffold.add_captions`-style
text splicing (never `yaml.dump`), then fit captions. Tests on fake
words as in `test_caption_lines.py`. Test on `test_story` by writing a
three-paragraph `script.txt` from the transcript preview above (Jacek
may replace it) and running `caption --apply`; every slide's words must
match its paragraph.

### 5. The path a person walks
- After `record --voice`, the guide's one step is `go` (ingest, init,
  caption, draft), not `init --force`: the narration is captioned
  without anyone knowing that captions are a step.
- The recording window, when `script.txt` is empty, says once:
  "Paste what you will say, one paragraph per picture, and each
  paragraph becomes one slide. Or just talk: the pictures change at
  your longest pauses."
- `film check` lists slides as `s01  16.2s  drift_left  1declaration…  ←
  voice 00:02.05–00:18.20  4 caption(s)`.
- HOW_TO_USE: one short section, "Photos with your voice over them",
  the three sentences above and nothing more.

### 6. Acceptance, on `test_story`, before saying "done"
`uv run film go -p test_story --rewrite --no-open`, then `film check`
and the draft, then this table filled in by measurement:

| check | expected |
|---|---|
| shot order | 1, 2, 3 |
| each slide's `in`/`out` | inside the narration, no overlap, the gaps are pauses |
| captions | on every slide, none "cut short" |
| `upload.txt` | chapter lines from the captions |
| narration end vs film end | the film ends 0.4 s + music fade after the last word, no silence beyond that |
| `film undo -p test_story` | brings back the version before |

Then the narration reordered by hand (swap s02 and s03 in film.yaml) and
a peek: the words must move with the pictures.

## Not in this plan
The voice chain, music bed and look (0003, 0007, 0008); the bench's
form (it moves whole shots, which is enough); anything about clips with
speech, which already work; the "clip with no speech: muted or music
level" question from the morning, still Jacek's to decide.
