# Plan, 2026-09-20: finish German Forgotten Bauhaus Hope, then make it repeatable

Written by Claude (Opus 5) on the evening of 2026-09-19, after Jacek's
first real film made with the intro → narrated photos → closing words
path. Same rules as before: `change-the-machine` for code (a test named
as a sentence first, one item per commit), `edit-pass` for the film,
measure before claiming. **P** is the producer, **D** the developer.

## What happened on 2026-09-19

Jacek walked the guide as a busy producer would. Every stop was a fault
in the machine, fixed and committed the same day:

| what Jacek hit | commit |
|---|---|
| photos after an intro: the guide never offered the narration; the numbered photos would have played before the intro | `206f892` |
| no idea what was already recorded; the narration window opened on the intro's words; closing the window kept a 2-of-10 narration as the real one | `0ddb038` |
| pasted words never reached the pictures; no way to leave a picture without words | `4c31d85` |

The film itself: 19 shots, 281.8 s. Edit pass on `film.yaml`:
- the German titles were on screen for under a second, now on the measured speech;
- the closing clips go from speed 1.2 to 1.0, because they were already spoken at 122 wpm, against 119 wpm for the narration.

**Final render** (ran at the end of 2026-09-19, exit 0):

| what | value |
|---|---|
| file | `projects/German Forgotten Bauhaus Hope/out/final.mp4` |
| length | 281.8 s |
| size | 666 MB |
| render time | 1091.6 s, about 18 min |
| loudness | -13.5 LUFS integrated, measured with ffmpeg `ebur128` on the file |
| cover and upload text | `out/cover.jpg`, `out/upload.txt` |

`film final` itself warns: "282s long, and a Short stops at 180s". See item 2.

## Late evening 2026-09-19: done after the plan was written

| what | commit |
|---|---|
| Cut to a Short: 281.8 s → 171.6 s, 8 cuts proposed and approved ("go") | `bfa7424` |
| `fit-to-length` skill, the precedent for new skills (`docs/decisions/0009`) | `dad6277`, `9a42922` |
| Look D on the talking shots: `fill: blur`, `fill_aspect: 0.8`, `glow 0.25 → 0.40`. Chosen by Jacek from `out/look_compare.jpg` | `474743c` |
| Skills `write-to-fit`, `status`, `fix-captions`, each done once on Bauhaus | `b0fb495` |
| Rehearsal script: 414 → 216 words, all 10 pictures, about 147 s estimated. `projects/German Forgotten Bauhaus Hope/write-to-fit_2026-09-19.txt` | not committed: the project's text files are untracked, see item 6 |

**Final render of the Short** (ran at the end of 2026-09-19, exit 0). It replaced the 4:42 final.

| what | value |
|---|---|
| length | 171.7 s, measured with ffprobe: a Short |
| size | 393 MB |
| render time | 803.7 s, about 13.4 min (the 4:42 version took 1091.6 s) |
| loudness | -13.2 LUFS integrated, ffmpeg `ebur128` |
| `upload.txt` and `cover.jpg` | rewritten at 18:12. The chapters now follow the Short |

Checked on three frames grabbed from the final:
- intro at 12.0 s and closing at 164.1 s: head and shoulders on blur, as chosen (look D);
- picture 3 at 73.8 s: the title "Hannes Meyer's Laubenganghäuser, 1930" is on screen.

On the talking shots, the lower caption line sits partly on the blurred
band under the picture. It is readable in the frames. Jacek to judge
whether it should move up.

## FIRST, 2026-09-20: lips out of sync in the second spoken part

Jacek, after watching the Short's final: "the second spoken part is out
of sync... I am still moving lips, it stays behind the soundtrack which
is faster. This 1.22 speed, is it not a problem?"

Use the `investigate` skill: measure first, no fix before the cause is
named.

**Known (from the file, not measured on the render):**
- The final has 5 talking shots. The intro (s01, s03) plays at speed 1.2.
  The closing (s15, s16, s17) was changed from 1.2 to 1.0 this evening,
  with its captions rescaled ×1.2.
- Also changed this evening on the same shots: `fill: blur`, and the
  dissolve into s15 removed.
- "The second part" most likely means the closing, s15–s17. Confirm
  with Jacek if the measurement doesn't settle it.

**Hypotheses, none checked:**
1. At `speed: 1.0` the picture and the sound take different paths.
   `audio.voiced_chain` applies `atempo` only when speed ≠ 1.0. Check
   that the picture side agrees exactly.
2. The sound was shaped once per take ("3 take(s) shaped once, 10
   piece(s) cut from them" in the render log), and a piece is cut at the
   wrong place when the speed changes within a take. Both takes had
   pieces at 1.2 in the earlier render.
3. At 1.2, the audio `atempo` and the picture step drift apart over a
   long shot (s01 is 25 s).

**Measure:** for one talking shot at each speed:
- pick a hard sound onset in the source, a plosive after a pause, found
  with `silencedetect`;
- find the same instant in the final: the audio onset, and the frame
  where the mouth opens;
- the offset in ms is the answer. Over about 80 ms is visible; the
  complaint suggests hundreds.

Do it for s01 (1.2) and s15 (1.0), early and late in each shot. That
separates the hypotheses.

Sound code is a standing request (`docs/decisions/0003`). Read it before
touching `audio.py`, and ask Jacek before changing anything there.

## Needs Jacek: what could not be tested tonight

Jacek could not record again tonight. Everything below needs his voice,
his eyes, or a decision.

1. **Watch the new final**: `out/final.mp4`, the Short with look D.
   - Does head-and-shoulders read better than the close-up?
   - Is glow 0.40 on the photographs too bright? The glow is film-wide,
     and I measured it only on the face.
2. **The recording window, never seen since today's fixes**, all
   checked on the next recording:
   - pasted text appears beside each picture when you press Start
     (`4c31d85`);
   - `-` and `[5]` in a real paste;
   - closing the window mid-narration shows "Stopped at picture N of
     10" and puts the take in `media\_discarded\` (`0ddb038`; the rule
     worked on a real take at 14:34, the review screen wasn't seen);
   - the "So far" line on the guide screen (`0ddb038`).
3. **The rehearsal script**: re-record Bauhaus with it (about 10 min of
   recording), or keep it as the template for the next film. If
   re-recorded, measure the real length: that is the second data point
   for the 1.47 words/s rate in `write-to-fit`.
4. **"Light,"** on picture 5 is on screen for 0.51 s. Left alone on
   purpose (one word between two pauses). Say if it bothers you.
5. **Item 4 below**, speed per take: the rule is still your decision.

## Items for 2026-09-20, in order

### 1. P: look at the final. 10 minutes
`projects/German Forgotten Bauhaus Hope/out/final.mp4`. Look for:
- the titles on pictures 3, 5 and 8;
- whether the closing words now sound like the narration;
- pictures 9 and 10, which are silent for 4.5 s each. Is that intended?
- s18, a 0.9 s last piece of the closing take with no words: a stray breath? Delete it if so.

### 2. DONE 2026-09-19 evening: cut to a Short, 171.6 s
Jacek said "go" to 8 cuts proposed by Claude (whole sentences and shots
said twice, none split). 11 shots, 171.6 s; peek rendered (`bfa7424`).
The 4:42 version is `0b24b8c` (`film undo`). **Left for P:** watch the
peek, then ask for `film final` (about 11 min at this length, reasoned
from 18 min for 281.8 s -- not measured). The method is now the
`fit-to-length` skill (`dad6277`), and the precedent for new skills
(`docs/decisions/0009`).

The original item, kept for the record:

### 2 (was). P decides: a Short or a regular video? 281.8 s is 4:42
YouTube Shorts go up to 3:00. As it stands, this uploads as an ordinary
vertical video. Two ways:
- (a) upload as it is;
- (b) `uv run film go -p "German Forgotten Bauhaus Hope" --target 180`.
  **But** `--target` never shortens anything spoken, and the speech alone
  is well over 3 minutes (measured: 63.6 + 111.3 + 44.9 s of talking,
  pauses excluded). So (b) can't reach 3:00 without cutting words. That
  is a script decision, not a machine one.

### 3. D: captions for words the transcriber does not know. Code
**Measured today:** the four German titles got captions of 0.42–1.14 s,
because the English transcriber heard only one or two words of each.
When I placed them by hand on the pauses measured with ffmpeg
`silencedetect`, they came out at 3.85–5.30 s.

Rule to build: when a script line is only partly heard, the caption spans
the speech between the neighbouring heard lines (the pauses measured in
the audio), not just the part that was heard. The test uses today's
numbers: s06 must come out near 45.35–50.66 s of the narration.

Worth measuring first, before building the rule: faster-whisper's
`initial_prompt`/`hotwords`, fed the script's own words. If it hears
"Laubenganghäuser" with that, the rule may be unnecessary.

### 4. D, P decides the rule: speed per take, from the measured pace
**Measured today:**

| take | pace |
|---|---|
| intro | 97 wpm |
| narration | 119 wpm |
| closing | 122 wpm |

A fixed 1.2 suited the first and rushed the last (146 wpm as played).
Proposal: `init` sets each take's speed to bring it near the
narration's pace, clamped to 1.0–1.2, and writes the measurement into
`note:`. P decides whether that is the rule, or whether 1.2 stays and is
changed by hand.

### 5. D: walk the whole path as the user, on a scratch copy
Three things in the recording window were built today and never *seen*.
I can't drive the microphone:
- the text appearing on Start;
- the "Stopped at picture N of 10" review screen;
- `-` and `[5]` in a real paste.

Jacek's next recording checks them. Before that, D walks every guide
screen on a scratch project: new → intro → photos → narrate → close the
window midway → reopen → narrate → closing words → go. Check what each
screen says and what each step leaves on disk. See the memory note
"walk the path as the user".

### 7. D: a word budget in the recording window. Code. Jacek said yes
**Why:** the only way to hit 3:00 without AI is to write to fit, before
recording. **Measured on one film:** German Forgotten Bauhaus Hope had
414 spoken words (intro 103 + narration 220 + closing 91) in 281.8 s,
which is 1.47 words per second of finished film. At that rate, 3:00 is
about 265 words for the whole film.

**Build:**
- the compose screen of both windows shows the words pasted, and what
  they come to next to the film's other takes: "310 words ≈ 3:31, a
  Short is ≤ 265";
- a pure function `booth.budget(words_here, words_in_other_takes)`,
  tested first;
- the rate is a named constant with this measurement in its comment.

Re-measure it on the next two films before trusting it.

### 6. P: tidy the working tree. 5 minutes
Not touched by Claude and left as found:
- `projects/test_story/script.txt` is modified;
- a dozen project folders and `script.txt` files are untracked;
- so is `.claude/settings.local.json.bak`.

Say which films should be in git.

## Not doing, unless asked

- The 20% caption rule: this film has captions over 73% of its runtime.
  That is right for a Short watched muted, so there is nothing to fix
  unless P says otherwise.
- The sound chain: a standing request, `docs/decisions/0003`.
