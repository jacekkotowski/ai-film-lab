# Production plan, 2026-09-16

Written by Claude (Fable 5.1) after measuring, for cheaper sessions to
execute one item at a time. Every number below was measured on this
machine on 2026-09-16 unless the line says *inferred*. The scripts that
produced them are in this folder; run them again before and after a
change, and paste the before/after table into the commit.

Two hats sign every item: **P** is the producer (does the audience feel
it?), **D** is the developer (can it be built small and kept?). Where
they disagree it says so.

Rules that apply to every item here:

- `ffilm/CLAUDE.md` and the `change-the-machine` skill: a test named as a
  sentence first, the smallest change, the whole suite, a commit that
  says why. Tests are pure functions only.
- The sound chain is opened by Jacek's request of 2026-09-16 for the items
  listed here and nothing else. The look pipeline (grain, vignette,
  scratches, flicker, their constants) is **not** to be touched.
- **Any change to the voice chain must bump `audio.VOICE_VERSION`**, or
  the cached `analysis/voice/*.wav` is reused and the change is inaudible
  (see item 6b). Until 6b lands, this is a rule to remember by hand.
- The film used for all measurements: `projects/I am not your fear`,
  take `rec_20260916-113221.mp4` (288 s, 1920x1080, 48 kHz), final of
  12:06 today (215.9 s, 1080x1920).

---

## Order of work

| # | Item | Why first | Size |
|---|------|-----------|------|
| 1 | **3. Re-reads have no caption** | 22 % of today's film is speech with no caption; it is a bug and a producer's finding at once | small (voice.py + cli print) |
| 2 | **4. Music loop** + **6c. Music level** | dead air in today's final at 3:14; two tracks 31 LU apart under one knob | small (audio.py music section) |
| 3 | **1. Noise: one measured experiment** (`arnndn`) | the only chain-side lever left; a go/no-go with numbers | small code, one download |
| 4 | **2. Voice character** (EQ block) | after Jacek picks a sample by ear | small |
| 5 | **5a, 5b, 5d, 6a, 6b, 8b** small fixes | each is one function and one test | tiny each |
| 6 | **9. Sharpen before warp** | judged on a draft; recordings only | small |

Left out on purpose: see the last section.

---

## 1. Background noise still audible

**Claim tested:** "0003's cause (the gate on the wrong scale) is back."

**Measured** (`measure.py`, 50 ms RMS windows, per 15 s block, whole take):

| stage | room (p10 of windows) | pauses, absolute | speech p90 | note |
|---|---:|---:|---:|---|
| raw take | −58.1 dBFS, block spread 2.3 dB | −55.0 dBFS | −26.2 | the room is flat across the take |
| chain output (`analysis/voice/…v4.wav`) | −92 in 15 of 16 blocks | −82.4 dBFS | −12.3 | gates close |
| voice-only mix, loudnorm −14 (music off) | −89 where pauses are long | −77.9 dBFS | −10.3 | pauses are silent |
| final with music | — | −31.9 dBFS | −10.2 | what is in the pauses is the ducked music |

So the premise is wrong: **the pauses are clean** (−78 to −82 dBFS) and
the room does not drift. What remains is **inside the phrases**: the
5th percentile of the un-gated windows on the chain output is
**−49.6 dBFS against speech peaks at −13.8**, i.e. the room between and
under words, 36 dB down, where a gate with a 250 ms release never closes.
Its spectrum is broadband with as much energy in 120–1000 Hz as above
(raw pause bands: 0–120 −6.4, 120–300 −5.4, 300–1k −6.3, 1–3k −8.7 dB
relative to its total): the same band as the voice, so the high-pass and
the de-hisser do not reach it.

Variants on a 34 s excerpt (take 20–54 s, `chain_f.py` style):

| variant | in-phrase floor | speech p90 | verdict |
|---|---:|---:|---|
| current chain | −49.6 | −13.8 | reference |
| `afftdn … :nr=24` | −49.7 | −13.8 | nothing |
| + `anlmdn` after afftdn | −49.9 | −13.7 | nothing |
| both gates release 90 ms | −41.9, 30 % gated | −13.8 | worse; it chops |

**Mechanism (measured):** the steady-state denoisers are at their floor;
the residual is the room under the voice, and 0004 already says what
moves that: distance to the mic (raw signal-to-room here is 29–32 dB;
0004 calls 40+ normal at 30 cm).

**The one thing left to try in the chain: `arnndn`** (RNNoise, a speech
model). It is in this ffmpeg (9.0.1) and needs a model *file* (`.rnnn`,
under 1 MB), not a package: the same pattern as the bokeh model in 0006.

Steps:
1. Ask Jacek to download one published RNNoise model into `models/`
   (list URL and SHA-256 in `models/README.md`, like the bokeh model).
   Do not download unasked.
2. Add a variant to `chain_f.py`: after `volume=…dB`, insert
   `aresample=48000,arnndn=m=models/<file>.rnnn,aresample=44100`
   (RNNoise is a 48 kHz model). Run the 34 s excerpt.
3. **Go** if the in-phrase floor drops by ≥ 8 dB *and* the speech bands
   3–6 kHz and 6–10 kHz move by ≤ 1 dB (consonants intact: 0004 §3 is
   what happens when a denoiser eats them). **No-go** otherwise: write
   `docs/decisions/0007` saying the residual is the room under the voice
   and the fix is the microphone, with the table above.
4. On go: add it to `lift_filters` (item 6a), bump `VOICE_VERSION`,
   test `test_the_speech_denoiser_runs_at_48k_and_comes_back`, render a
   draft, ask Jacek to listen.

**P:** the audible win is real only if step 3 passes; do not ship a
denoiser that costs consonants for 3 dB. **D:** one filter, one data
file, no dependency; the measurement is the whole cost. Agreed.

## 2. Deepen and warm the voice, clearer consonants, softer

**Measured** (same 34 s excerpt; bands are dB relative to the speech's
own total; samples `listen_*.wav` were sent to Jacek):

| variant | in-phrase floor | p50 | 100–300 | 3–6k | 6–10k |
|---|---:|---:|---:|---:|---:|
| A current | −49.6 | −26.5 | −3.7 | −13.8 | −21.7 |
| G: EQ only (`lowshelf f=180 g=2`, `equalizer f=3200 q=1 g=2`, `highshelf f=9000 g=-2.5`) | −48.6 | −25.5 | −3.1 | −13.6 | −23.0 |
| F2: G's presence + `deesser` + `acompressor thr −20 dB ratio 2.5 makeup 2` + shelf | −44.1 | −21.4 | −3.5 | −11.5 | −20.9 |

Reading: EQ alone moves the tone and leaves the room where it was. The
compressor is what "fuller" is (p50 +5 dB) **and it lifts the room
between words by the same 5.5 dB**. So compression waits for item 1.

Reverb: `aecho` is a slapback, not a room; the gates then chop its tail;
on a phone speaker a talking-head Short with reverb reads as a bathroom.
Left out. If ever wanted: `afir` with a short impulse-response wav kept
in `library/` (a data file). No library earns a fifth package for any of
this; everything is in ffmpeg.

**Decided 2026-09-16: F2 is the chain.** Jacek chose it by ear, and
also said he is half deaf (artillery). So this item is not judged by
listening again, by him or by a session: it is judged by the table
above, and the compressor is *in*, because compression is what carries a
voice on a phone speaker and for listeners who lose quiet syllables.
Its cost (+5.5 dB of room between words) is why item 1's denoiser test
runs on **this** chain, not on the old one.

Steps:
1. Put the EQ into `audio.voice_tone()` (it already holds the 80 Hz
   floor and the 110 Hz warmth; these are three more lines of the same
   kind), constants beside `VOICE_WARMTH_DB` with a one-line reason each:
   `lowshelf=f=180:g=2`, `equalizer=f=3200:width_type=q:w=1:g=2`,
   `highshelf=f=9000:g=-2.5`.
2. After **both gates** (they must see the ungated signal first, and the
   de-esser must see the gated one): `deesser=i=0.3:m=0.5:f=0.5`, then
   `acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2`.
   Both ride with `speech_lift`.
3. Bump `VOICE_VERSION`. Test: `test_the_voice_tone_is_the_same_on_both_chains`
   (falls out of item 6a) and `test_the_character_block_comes_after_the_gates`.
4. Acceptance, by numbers (`chain_f.py`, 34 s excerpt): p50 within 1 dB
   of −21.4, 3–6 kHz band within 1 dB of −11.5, p90 between −15 and −13.
   Then a draft of s01; the note in the commit says what changed.

**P:** wants the density and gets it. **D:** accepts the +5.5 dB of room
only because item 1 is measured on top of it next; if item 1 is a
no-go, drop `makeup` to 1.4 and re-measure, do not drop the compressor.

## 3. Bug: a repeated caption does not show up

**Measured** on today's film (`fluffs.py`): 48 transcript lines became
48 captions, and yet **8 talking shots have no caption at all**:
s07, s09, s13, s15, s16, s18, s21, s23 — **47.5 s of 215.9 s, 22 % of
the film**. Each sits in a stretch where the transcript has no line
(84.5–101.7, 123.5–135.3, 186.2–203.9, 210.2–219.4, 222.0–234.4,
270.2–278.6 s of the take), and each is followed by the same sentence
read again, captioned. So what the viewer sees: the line is said with no
caption, then said again with one.

**Mechanism (measured in code and reproduced):** `voice.align_to_script`
keeps only the *last* reading of each written sentence
(`FALSE_START_GAP`, the "run" loop: "a sentence read twice keeps the LAST
reading"). `scaffold` keeps every spoken piece as a shot. The two halves
disagree about whether the first reading exists. The pure path for a
sentence that is *written* twice is fine: five cases run
(repeated unit, refrain three times, consecutive repeat, fluffed first,
false start then full read) all came out captioned. Re-fitting every
project's saved transcript to its film placed every line (24/24, 23/23),
so nothing is lost in `caption_fit`.

Fix, regardless of the rest:
1. In `align_to_script`, after the monotone match, for every unit take
   the spoken stretches that matched nothing and run
   `SequenceMatcher(unit_tokens, stretch_tokens)`; where `ratio() ≥ 0.6`
   emit a second `Line` with the unit's text over those words. Keep the
   existing last-run Line as it is. Test:
   `test_a_sentence_read_twice_is_captioned_twice` (build fake words
   with `.word/.start/.end`, see the `W` class in
   `tests/test_caption_lines.py` for the pattern).
2. `film caption` prints a re-read list from the placed captions: shots
   whose caption texts all reappear on a later shot, with seconds:
   `re-reads: s07 (10.5s) s09 (7.0s) … 47s. Delete the earlier one if
   the second is the keeper.` Pure function `caption_fit.re_reads(placed)
   -> list[(shot_id, seconds)]`, test
   `test_a_re_read_is_named_with_its_shot_and_its_seconds`.
3. Acceptance: `uv run film caption -p "I am not your fear" --apply` →
   every talking shot has captions; the report names the eight shots.
   Then one **edit-pass** to cut them (s23 is a 0.7 s tail; check what is
   said before cutting).

**P:** cutting the re-reads is the single biggest improvement available
to this film, and it is an editing decision, so the machine reports and
the editor cuts. **D:** the alignment change is ~20 lines in one
function, the report is pure. Agreed.

## 4. When the music runs out before the film

**Current behaviour** (`audio.build_soundtrack`, the music section):
`-stream_loop -1` when the track is shorter than the film; the seam is a
hard join of the track's own tail to its own head; no crossfade;
`_dur()` failing returns 0, which means *no* loop and a hard end.

**Measured** on today's final. Own track 195.7 s, film 215.9 s, so it
looped once at 3:15. Music-only bed (`music_only.py`): silent (< −50 dBFS)
from 0.0–9.75 s (the track's own quiet intro, under the title card) and
**from 188.0–205.5 s: 17.5 s with no music** (the track's tail fades to
−93 dBFS by 193.4 s, the loop restarts at 195.7 s with 1.2 s of digital
silence and a slow intro). In the final, 194.0–194.75 s measures
−88 dBFS: dead air.

Design against the hard cut:
1. Trim the track's own silent head and tail before anything else:
   `silenceremove=start_periods=1:start_threshold=-50dB:stop_periods=1:stop_threshold=-50dB`.
2. Loop by giving ffmpeg the file `ceil(total / mdur)` times as separate
   inputs and joining them with `acrossfade=d=3:c1=tri:c2=tri`, then the
   existing trim/volume/fades. No `-stream_loop`. Pure planner
   `music_plan(mdur, total) -> repeats` with a clamp (a 5 s jingle under a
   10-minute film is 120 repeats: cap at, say, 12 and say so). Tests:
   `test_a_track_shorter_than_the_film_is_repeated_with_a_crossfade`,
   `test_a_track_longer_than_the_film_is_played_once`,
   `test_an_unmeasurable_track_is_played_once_and_said_so`.
3. `checks.library_lines`: append `-- 195.7 s of music under a 215.9 s
   film: it repeats once, crossfaded` when it will.
4. Acceptance: re-run `music_only.py`; no stretch below −50 dBFS longer
   than 3 s between 5 s and total−5 s.

**P:** dead air in a Short is a scroll-away; the intro-under-title-card
silence (item 1 of the table) is the track's own choice and stays.
**D:** ~25 lines in one section plus a pure planner. Agreed.

## 5. Every user-facing step, as a first-time user

Walked: `HOW_TO_USE.md`, `FILM.bat`, `uv run film` (the walk), `film
--help`, `film check`, the five skills. The order is right and the guide
does lead. What a first-timer hits:

- **5a. Default names come out mangled on the thumbnail and the opening
  card.** Press ENTER at "A name for it" → `Night_2026-09-05_2` →
  `spec.pretty_name` splits on `-` too → the rendered card reads
  **"Night 2026 09 05 2"** (rendered, `cover_audit.py`). Fix in
  `pretty_name`: split on `_`, and on `-` only when not between two
  digits. Test `test_a_date_in_a_folder_name_keeps_its_hyphens`;
  `"morning-walk" -> "Morning Walk"` must still pass.
- **5b.** The walk's prompt reads `2-2 for another` when there is one
  alternative (`guide.walk`, the `choices` string). Say `2 for another`
  when `len(steps) == 2`.
- **5c.** `film caption --help` says "transcribe a voiceover into
  captions". A first-timer has no voiceover; they talked into the
  camera. Say: "put what you said in your clips on screen (or a
  voiceover)".
- **5d.** `film init` signs the file with `# Speech captions are left out
  on purpose -- run uv run film caption`, and it is still there after
  `go` has added 48 captions (today's film.yaml). `scaffold.add_captions`
  should drop those three footer lines when it writes captions. Test
  `test_the_footer_stops_saying_captions_are_missing_once_they_are_in`.
- **5e.** The `film --help` header list omits `go` and `record`, the two
  commands the guide leads with. Two lines in `cli.py`'s docstring.
- **5f.** See 8b: a portrait picture in a wide film's `cover/` is cropped
  to a band and nothing says so.

Not changed: the ordering of steps, the skills' wording, HOW_TO_USE.

## 6. Code health: fragile files, actual risk

- **6a. `audio.py`: the voice chain is written twice.** `voiced_chain`
  and `speech_chain` (the fallback) list the same seven filters in the
  same order. A change to one and not the other diverges silently on
  the path that only runs when voicing a take failed. Extract
  `lift_filters(tuning) -> list[str]` and call it from both. Test
  `test_the_fallback_chain_shapes_the_voice_exactly_like_the_voiced_take`.
- **6b. `audio.py`: the voiced-take cache ignores the tuning.**
  `voiced_path` is keyed by file, speed, lift and `VOICE_VERSION`;
  `voiced_take` rebuilds only when the source file is newer. Re-ingest
  (new `room_db`/`voice_db`) or any constant change without a version
  bump reuses the old wav, and the person listening concludes the change
  did nothing. Put the three tuning numbers (rounded to 0.1 dB) and a
  short hash of the filter string into the filename. Test
  `test_a_different_tuning_is_a_different_voiced_take`. This removes the
  hand rule at the top of this plan.
- **6c. The constant that should adapt: the music bed's level.**
  Measured with ebur128: the project's track is **−13.5 LUFS**, the
  library's `tibetan_cafe.m4a` is **−44.3 LUFS**: 30.8 LU apart under the
  same `music_volume: 0.6`. So the knob means "loud" on one film and
  "nearly absent" on another, and the duck arithmetic (`KEY_LEVEL_DB`,
  `duck_threshold`) assumes a bed level nothing measures. Do for the
  music what 0003 did for the voice: measure the track once
  (`take_gain_db` already does this for a take; reuse it), gain it to
  `MUSIC_TARGET_LUFS = -24.0` **before** `volume=music_volume`, clamps
  like `level_gain`. Pure `music_gain(measured_lufs)`, test
  `test_a_quiet_track_and_a_loud_track_land_on_the_same_bed_level`.
  Then 0.6 is 0.6 on every film.
- Stays fixed, and why: `loudness −14` (the platforms'), `GATE_FRACTION`
  (tied to `ingest.QUIET_FRACTION`, by design), `VOICE_AT_GATE_DBFS`
  (held across four attenuations, per the note in audio.py).
- Not touched: `cli.cmd_go` holds workflow logic against the rulebook;
  moving it is tidiness, not risk. `scaffold.py` (813 lines) was not
  read for this plan; no claim about it.

## 7 and 10. Innovation, constrained to the four packages

What a bigger crew would have caught on this film, in order of impact:

1. **The film contains its own outtakes** (22 %). Item 3 makes them
   visible; one edit-pass removes them. Nothing to build beyond item 3.
2. **The bed is not level-matched** (31 LU). Item 6c.
3. **The opening card is four seconds of a Short before a word is
   said.** *Inferred*, not measured: the first sentence is the hook. Make
   `film init` write `duration: 2.0` for the card on vertical films
   (`scaffold`, the s00 block), and say in the note that 0 removes it.
   One number.
4. **Caption safe zone on Shorts.** *Inferred*: `lower_third` sits at
   0.72 h and a three-line block reaches ~0.87 h; the Shorts overlay
   (title, channel, the like/comment rail) covers roughly the bottom
   fifth and right tenth. Verify first by uploading one unlisted Short;
   if confirmed, `render.caption_art` gets a vertical-film y of 0.62 for
   `lower_third`. Not before it is seen.
5. **`film check` says how much of the runtime is captioned**, against
   the 20 % taste rule in `projects/CLAUDE.md`. Pure, one line. Low.

Not proposed: B-roll automation, automatic cutting of re-reads,
generated voices, anything needing a package.

## 8. Title and cover, end to end

**Measured** (`cover_audit.py`, six cases incl. a folder with no
`cover/`):

| case | picture chosen | title | as documented? |
|---|---|---|---|
| no `cover/` folder, 1080x1920 | shelf `vertical.png` (1023x1537) | folder name | yes |
| empty `cover/` (Night_2026-09-05_2) | shelf `vertical.png` | "Night 2026 09 05 2" | picture yes; **title mangled (5a)** |
| own picture, tall film (I am not your fear) | own, 1023x1537 | folder name | yes |
| own picture, wide film (Prayer for Her) | own **1122x1402 portrait** on 1920x1080 | folder name | picture yes, **cropped to a band; the face is cut** (rendered) |
| `title:` in film.yaml | — | none of the 12 projects sets one; the code path is `headers()` and works in the test suite | yes |
| shelf `bak/` subfolder, `.on1` sidecar | ignored (files only, `POSTER` set) | | yes |

Two things the docstring does not say:

- **8a. Staleness ignores the picture.** `is_stale` and `refresh_card`
  compare only against `film.yaml`'s mtime. Measured: after dropping a
  new picture into `cover/`, `refresh_card` returned the old card and
  `choose` already returned the new picture. Fix: compare against
  `max(mtime(film.yaml), mtime(backdrop))`. Test
  `test_a_new_cover_picture_rebuilds_the_card`.
- **8b. Own picture wins regardless of shape.** By design ("never
  letterboxed"), but nothing says so. `checks.library_lines`: when
  `library.is_wide(back.path) != (w >= h)`, append `(portrait picture
  on a wide film: the top and bottom are cropped; a wide one in cover/
  would fit)`. No behaviour change.

**P:** 5a is the one a viewer sees; 8b is the one Jacek saw on Prayer for
Her. **D:** three one-line changes. Agreed.

## 9. Making a face read better, without fighting the look

**Measured** on the real 1920x1080 frame at 1:00 (5 reps each):

| candidate | ms/frame | note |
|---|---:|---|
| `bilateralFilter d=9` | 54.2 | too slow |
| half-res bilateral d=7 + upscale | 11.2 (17.6 at 1080x1920) | cheap |
| MediaPipe person mask | 11.1 | already paid when `bokeh` is on |
| unsharp σ1.5 ×0.4 | 6.3 | |
| `apply_look` old_film+glow at 1080x1920 | 69.2 | for scale |

The vertical crop keeps 607 of 1920 px, so the face is **upscaled
1.78x**. Laplacian variance of the face region at output size: plain
7.1, sharpen-before-warp 9.9, **smooth-before-warp 3.5**. The face is
soft from the upscale, not textured. Skin smoothing makes it mushier and
the grain then paints texture back on top: **those two do fight, on this
footage. Not proposed.**

What reads better: a light unsharp on the *source frame before the warp*
(σ 1.2, amount 0.35; the crops `vert_*.png` show it), 6 ms, and it must
sit **before `apply_look`** so grain, scratches, flicker and vignette are
untouched. Place it in `render.VideoSource.frame` after the bokeh blend
and before the warp, **recordings only** (`kinds.is_recording`), masked
by the person mask when bokeh is on (sharpen the person, not the blurred
room). One constant `SHARPEN = 0.35`, a `sharpen:` per-shot override is
not needed yet. Exposure: `glow` already exists.

Test: pure `sharpen(frame, amount)` with `amount=0` returning the frame
untouched, and `test_only_recordings_are_sharpened`. Acceptance: draft
of s01 before/after; if webcam noise comes up with it, 0.2. On a wide
film there is no upscale and the argument is weaker: keep it to
recordings and ≤ 0.35.

**P:** wants the face crisper in the 9:16 crop; that is the upscale, and
sharpening is the honest answer. **D:** 6 ms, one function, before the
look. Agreed; smoothing refused by both.

---

## The two or three to do first

First, item 3: caption every reading and print the re-read list, then
one edit-pass on "I am not your fear" that cuts the 47 s of re-reads.
That is the largest change an audience will feel, it fixes the reported
bug, and it is a day of a cheaper model's work at most. Second, the music
section of `audio.py` in one go: silence-trimmed, crossfaded repeats and
a level-matched bed (items 4 and 6c), because today's final has 17 s of
dead air and the knob means something different on every film. Third,
the `arnndn` go/no-go of item 1: one download with Jacek's go-ahead, one
run of the script, and either a filter or decision 0007; only after that
the EQ of item 2, once Jacek has picked a sample by ear.

## Left out on purpose

Reverb (a slapback in ffmpeg, and the gates chop its tail); compression
(measured +5.5 dB of room between words; it waits for the noise
decision); skin smoothing (measured: it softens a face that is already
upscaled 1.78x); any fifth package (the two things that looked like they
needed one, RNNoise and an impulse response, are data files); moving the
Shorts caption line before seeing an upload; automatic cutting of
re-reads (the machine reports, the editor chooses); moving `cmd_go` out
of `cli.py` (tidiness, no measured risk); anything in the look pipeline
or its constants; and every speed idea in 0002. Cheap and minimal beats
complete: each item above is one function, one test, one commit.
