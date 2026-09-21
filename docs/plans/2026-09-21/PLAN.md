# Plan, 2026-09-21: a second film on the new rails, and three things left open

Written by Claude (Opus 5) late on 2026-09-20, after Jacek made
**1930s Austria Had Photoshop** end to end in one evening. Same rules as
before: `change-the-machine` for code (a test named as a sentence first,
one item per commit), `edit-pass` for the film, **measure before
claiming**. **P** is the producer, **D** the developer.

Jacek is busy on 2026-09-21 producing new material and has said he will
not have time for corrections. So this plan is ordered for that: what a
new conversation must know, then what can be done without him.

---

## Read this first: how 2026-09-20 actually went

Jacek's own words during the session, in order:

> "I gave up today"
> "i cannot sit and enter all the time!!!"
> "I told you and you did not change it"
> "so why do you oppose 1.2 for slides?"
> "Why is 'always when you record me do the 1.2 speed' such a problem
> consuming a tonne of tokens?"
> "instead of solving problems you introduce new ones?"

Every one of those was earned. The pattern, named so the next session
does not repeat it:

**Claude asserted instead of measuring, three times, and each time it
cost Jacek a round of arguing for something he should have got at once.**

The worst of them: asked for `speed: 1.2` on the narration, Claude read
*one* half of the code (`spec.py`, where a slide's duration ignores
speed), inferred the other half, and told him 1.2 would drift the sound
4.6 s away from the picture. It does not. `audio.speech_specs` passed a
hard `1.0` and never saw the number at all, so `speed:` on a slide was a
**dead key** — it did nothing and said nothing about doing nothing.

`ffilm/CLAUDE.md` already says reasoning from code has given four
confident wrong answers in this repo. This was the fifth. **Run the
thing. Every time.**

## What shipped on 2026-09-20

| what | commit |
|---|---|
| A take you numbered is still a take | `de9c9cd` |
| Every way of recording stays on the menu | `97b82bd` |
| "So far" lists what you recorded in the order you recorded it | `521d9e6` |
| A shortened caption says which caption it shortened | `6a356cf` |
| write-to-fit: a second measurement, and it disagrees with the first | `6623396` |
| A picture wider than the frame is travelled, not cropped | `5168f1c` |
| Your narration is you talking, so it plays at the same speed | `7a18940` |

Plus `docs/decisions/0010-your-narration-is-you-talking.md`.

307 lines added across 7 modules, no new dependencies, layer test green,
whole suite green.

### What is now automatic, and was not this morning

A new film gets all of this without anybody asking:

1. **1.2 on everything Jacek speaks** — talking takes *and* the narration
   over photographs. `speed:` on a slide is now a live key that shortens
   the picture and speeds the words by the same factor.
2. **Any picture the frame would crop is swept left→right.** Threshold is
   "anything at all", because a 1024x1536 diagram in a 1080x1920 frame
   loses 15.6% of its width and on these diagrams that is the whole
   right-hand column of labels.
3. **Every recording step stays on the guide's menu.** Before this, with
   photos in and no narration, no screen anywhere offered the camera —
   which is how Jacek lost the intro by pressing ENTER once.
4. **A numbered take keeps its 1.2, its sharpening and its bokeh.**
   Renaming a file to move it used to silently strip all three.

## The film: 1930s Austria Had Photoshop

Vertical Short, 9 shots, **142.2 s**, 46 captions (81% of runtime — right
for a muted Short). Everything spoken at 1.2. All five pictures swept.

**A `final` render was running when this plan was written.** First thing:
check `out/` holds `final.mp4`, `cover.jpg` and `upload.txt`. If only
`final__silent.mp4` is there, the render died partway — rerun it.

Measured pace, per block, from the takes:

| block | recorded | played at 1.2 |
|---|---|---|
| intro | 102 wpm | 122 |
| narration | 110 wpm | 132 |
| closing | 97 wpm | 117 |

Jacek asked whether 1.2 is too fast for a slow speaker and was told: no —
102–110 wpm is below conversational (120–150), so 1.2 makes him normal,
not fast. He said "it is ok" and rendered.

**Left on the table, his decision, not done:** a single multiplier cannot
even out three takes recorded at three paces. The narration is the
*fastest* block at 132 and also the densest content. `1.2 / 1.1 / 1.2`
would give 122 / 121 / 117 — a 5 wpm spread instead of 15. Two numbers.
Offer it once; do not do it unasked.

---

## Items for 2026-09-21, in order

### 1. P: the new material. Everything else waits on this
Jacek is shooting tomorrow. The whole point of the four automatic rules
above is that this film should need none of last night's corrections.

**What to watch for, because it is the first film built on the new
rails:**
- do the pictures sweep, and does the sweep look like a camera move
  rather than a wobble on the ones that are only slightly too wide?
- does his voice sit at one pace across intro, narration and closing?
- does `film init` write `speed: 1.2` on the slides, as it did on a
  scratch rebuild?

If any of those is wrong, it is a `change-the-machine` job, not an edit.

### 2. D: feed the script to the transcriber. Code. Asked for
**Measured 2026-09-20:** the intro's first caption came out "When you
click **on sharp mask** in photoshop". `voice.py` has no `initial_prompt`
and no `hotwords` — the transcriber never sees the script Jacek read
from, so a term it does not know is a term it will mangle.

This was fixed by hand in two places (`film.yaml` and
`analysis/transcript.json`), and it will happen again tomorrow on
whatever tomorrow's unusual words are.

This is the first half of item 3 in the 2026-09-20 plan, still unbuilt.
`faster-whisper` takes `initial_prompt` and `hotwords`. The project has
`script.txt` and `narration.txt` sitting right there. **Measure first**:
feed the script's own words and see whether "Unsharp Mask" survives,
before building any rule about partly-heard lines.

### 3. D: the write-to-fit rate is now wrong twice over
Three measurements, none agreeing, and the third is the important one:

| film | words | finished | words/s |
|---|---|---|---|
| German Forgotten Bauhaus Hope | 414 | 281.8 s | 1.47 |
| 1930s Austria, at the old speeds | 296 | 161.6 s | 1.83 |
| 1930s Austria, at 1.2 throughout | 296 | **142.2 s** | **2.08** |

The skill still says plan with 1.47, which now over-estimates length by
**40%**. A 3:00 Short is about **374 words** at the new default, not 265.
Jacek wrote 275 and landed at 2:22 with 38 s to spare.

The rate is not a constant — it moves with the speed default and with how
many silent picture-holds a film has. Either re-derive it from
`REC_SPEED` and the picture count, or stop calling it a constant and give
the skill a range. Do not guess a fourth number; tomorrow's film is the
data point that settles it.

### 4. D: `caption --apply` adds, and that lost a hand-edit
**Found 2026-09-20, the hard way.** `--apply` is documented as additive
("existing captions on affected shots are kept, new ones are added after
them"). Run it twice and every caption is doubled — it went to 159% of
runtime before anybody noticed.

The workaround used was: strip every `captions:` block out of the file by
hand, then apply once. That worked, **and it silently reverted a
hand-corrected caption**, because re-applying regenerates from
`transcript.json`.

Two things wrong, neither fixed:
- there is no `--replace`, so re-placing captions after a speed change
  means hand-editing YAML;
- a hand-corrected caption has nothing protecting it from the next
  regeneration.

Item 2 above (hotwords) would remove most of the need for hand
corrections and is the better first move.

### 5. P: two things in the film nobody has decided
- **s02 is 0.8 s of Jacek not talking** — a scrap of the intro take,
  no captions, between the intro and the first picture. A stray breath.
  The same artefact was flagged on Bauhaus in the 2026-09-20 plan (item
  1, s18) and never resolved either time. It is in the render that was
  running. Deleting the block is a four-line edit.
- **`5_example.jpg` is 600x260** and gets upscaled about 7x to fill the
  frame. The sweep shows the whole triptych now, but it will be soft in
  the final. Only a bigger source fixes it; a drop-in replacement needs
  no edit.

### 6. P: the working tree, and one decision that is Jacek's alone
Carried from the 2026-09-20 plan, item 6, still open. **This repo is
public** (`github.com/jacekkotowski/ai-film-lab`).

Nothing private is in git today: **0 media files tracked**, 15 text files
under `projects/`. `.gitignore` already excludes `media/`, `music/`,
`cover/`, `out/` and `analysis/`.

What is untracked and noisy: `script.txt`, `narration.txt`, `.vertical`
and `write-to-fit_*.txt` across 19 projects. Committing them would tidy
`git status` — **and would publish the words of `Prayer for Her`,
`I love you` and `I am not your fear` to a public repository.**

Two of them (`test_story`, `Mother and Child 2026-09-08`) are already
tracked, so the precedent is mixed.

**Do not decide this for him.** Three options, his call:
(a) commit them all — tidy, and public;
(b) add them to `.gitignore` — tidy, and they are then backed up by
    nothing;
(c) commit the working films, ignore the personal ones.

### 7. D, carried and still open: lips out of sync in the closing
**This was item FIRST in the 2026-09-20 plan and was never done.** It is
carried a second day.

Jacek, on the Bauhaus Short: "the second spoken part is out of sync... I
am still moving lips, it stays behind the soundtrack which is faster.
This 1.22 speed, is it not a problem?"

Use the `investigate` skill. The hypotheses and the measurement recipe
are written out in `docs/plans/2026-09-20/PLAN.md` — do not re-derive
them. **New information from 2026-09-20 that bears on it:** slides now
apply `atempo` where they previously did not, so if the complaint is
about a *narrated picture* rather than a talking take, the cause has
changed underneath the report. Establish which shot he meant first.

Sound code is a standing request (`docs/decisions/0003`). Read it before
touching `audio.py` and ask before changing anything there.

### 8. D: tidy after yesterday's edits
Two things Claude left behind, neither breaking anything:
- **Comment density in the new code is 31%**, against the house's 11–13%
  (`moves.py` 13%, `scaffold.py` 11%). Several comments are longer than
  the code they explain. Worth one trimming pass in the same voice as the
  file around them.
- **Three commits read as whole-file rewrites** (`guide.py` shows
  1003 insertions / 916 deletions for a real change of 89 / 2; same shape
  on `kinds.py` and `scaffold.py`). It is **not** line endings, not
  double-CR and not trailing whitespace — all three were checked and
  ruled out. Cause unknown. It makes `git blame` on those three files
  useless for yesterday. Worth ten minutes with `git diff --word-diff`,
  not more.

## Not doing, unless asked

- The 20% caption rule: this film is at 81%, correct for a muted Short.
- The sound chain: standing request, `docs/decisions/0003`.
- Per-take speed from measured pace (2026-09-20 plan item 4): partly
  superseded by decision 0010, which put everything spoken at one
  multiplier. The remaining idea — even out the *pace* rather than the
  multiplier — is described under "The film" above and is P's call.
- Ideas parked and never started: Hypothesis tests, CI.

---

# What actually happened on 2026-09-21

Appended at the end of the day. Jacek produced **Why there are wars** and
**published it**. Two items off the list, and one new fault found that is
worth more than either.

## Done

| item | outcome |
|---|---|
| 7. lips out of sync | **Measured. There is no sync fault.** `docs/decisions/0011`, commit `a47eacc`. Carried twice for nothing |
| — | Bauhaus closing `s15-s17` put to 1.2 at Jacek's instruction; 171.6 s → 166.2 s. `out/final.mp4` is **stale** |
| 3. the write-to-fit rate | third data point: **1.66 words/s** (240 words, 144.8 s). Not 1.47, not 2.08 |
| 5. the stray breath | gone again, as a side effect. Third film running |

**The film:** vertical Short, 8 shots, **144.9 s**, −13.3 LUFS,
rendered 13:04 in 473.6 s, `cover.jpg` and `upload.txt` written.
Uploaded by Jacek the same afternoon.

## The write-to-fit rate is not a constant, and now there are three

| film | words | finished | words/s |
|---|---:|---:|---:|
| German Forgotten Bauhaus Hope | 414 | 281.8 s | 1.47 |
| 1930s Austria Had Photoshop | 296 | 142.2 s | 2.08 |
| **Why there are wars** | **240** | **144.8 s** | **1.66** |

All three are at different picture-hold densities. Stop calling it a
constant. Give the skill a range, or derive it from `REC_SPEED` and the
silent hold time. Do not pick a fourth number.

## NEW, and the reason today's film shipped with a defect

**Two faults reached the published film. Neither was reported by
anything.** Both are the same shape: *the machine produced something
obviously impossible and said nothing.*

### A. Captions placed on spans that cannot hold them

Take 1's transcript came back with the right **words** and junk
**times** — 0.26 s for a ten-word sentence:

| line | span given | time to say it |
|---|---:|---:|
| "Coalition creates the capacity for violence." | 0.44 s | ~3.4 s |
| "And identity and moral commitment can lead people to resist." | 0.26 s | ~5.7 s |

`film caption` placed them anyway. Jacek watched a draft and reported
"the intro has no captions". Fixed by moving the intro to the complete
second take, whose spans agree with the audio to within 0.1–0.35 s.

**This is not what item 2 of this plan predicts.** Hotwords fix
mis-*heard* words. Here every word was heard correctly. Feeding the
script to the transcriber would not have caught this, and item 2 should
not be expected to close it.

### B. The film said the same sentence twice, three times over

1. `init` put take 1 as the intro **and the whole of take 2** as the
   closing. Take 2 re-reads the four intro sentences, so the film said
   them at 0:02 and again at 2:20. Caught before publishing; 165.4 s →
   144.8 s.
2. `s06` shows and **says** "Participation → changed attitudes and
   behavior → escalation." twice, at 1:40 and 1:44. Measured in the
   narration: two real speech blocks, 101.65–106.11 and 106.62–109.21,
   both inside `s06` (101.65–109.40). Jacek re-read the line; nothing
   noticed. **This is in the published film.**
3. The same doubling was in `upload.txt`, so it is in the YouTube
   chapters too.

`fit-to-length` exists as a *skill* for cutting what is said twice. There
is no *check*.

## The one change worth proposing, not yet asked for

`film check` should refuse to stay silent about both:

- **a caption that cannot be read** — on screen under ~1.2 s, or with
  fewer than half as many word times as it has words. The rule already
  exists, written down in the `fix-captions` skill, and it caught every
  bad caption on Bauhaus and on this film. It has simply never been code.
- **the same caption text twice in one film**, naming both shots.

Either one would have put today's two defects on screen before the
render, not after the upload. Neither is a change to the sound chain.
**Ask Jacek before building it** — `ffilm/` is not to be touched unasked.

## Still open, untouched today

Item 2 (hotwords), item 4 (`caption --apply` doubles), item 6 (the public
repo and the personal `script.txt` files — still his decision alone),
item 8 (comment density, the three whole-file-rewrite commits).
