---
name: write-to-fit
description: Before recording, turn the producer's notes and photos into three texts written straight into the files the recording windows open (script_intro.txt, narration.txt, script_outro.txt) — the intro for the camera, one narration paragraph per picture, the closing — inside a word budget for the target length (a Short: about 265 words). Checks each paragraph against its photo. Use when the user says "write the script", "help me with the text", "I have photos and notes", or starts a film with a length in mind.
---

# Write to fit: the length is decided before the microphone is on

After recording, getting under 3:00 means cutting the user's words
(`fit-to-length`). Before recording it is only writing. This skill
prevents three faults found on 2026-09-19:
- the film was too long (281.8 s);
- 8 texts were written for 10 pictures;
- three pictures of the same walkways got texts that repeated each
  other.

Done first on 2026-09-19 as a rehearsal on German Forgotten Bauhaus
Hope, after it had been recorded. The recorded texts had 414 words, and
the film was 281.8 s. Rewritten: 216 words, all 10 pictures, every point
of the argument once. Estimated at about 147 s, not measured.

## The budget

Two films measured, and they do **not** agree:

| film | words | finished | words/s | pictures |
|---|---|---|---|---|
| German Forgotten Bauhaus Hope, 2026-09-19 | 414 | 281.8 s | **1.47** | 10 |
| 1930s Austria Had Photoshop, 2026-09-20 | 296 | 161.6 s | **1.83** | 5 |

25% apart, so **plan with 1.47 and expect to come in short.** That is the
safe direction: 1.47 over-estimates the length, and a film that lands
under its target needs nothing done to it, while one that lands over
costs an evening of cutting.

| target | words at 1.47 (plan with this) | at 1.83 (the optimistic end) |
|---|---|---|
| a Short, 3:00 | about 265 | about 329 |
| 2:00 | about 175 | about 219 |

Worked example: 275 words were planned at 1.47 → 187 s, and came out at
161.6 s. 16% short.

**The likely cause, not yet measured:** Bauhaus held 10 pictures, two of
them silent for 4.5 s each; this one held 5 and was cut tight. The
silent holds, the title card and the gaps between paragraphs are all
film that carries no words, and there is more of that per word in a film
with more pictures. If that is right the rate belongs per-picture, not
per-film. Do not build that until a third film says so.

Re-measure on every new film and add a row.

## Steps

1. **Look at the pictures**, `analysis/contact.jpg`. If the film hasn't
   been ingested yet, run `uv run film ingest -p NAME` first.
   - The order is `scaffold.pictures_in_order`, which the narration
     window also uses.
   - Say what each picture shows, in a few words.
   - Name any pictures that show the same thing. Their texts must not
     repeat.

2. **Read what the user gave**: notes, an old `script_intro.txt`,
   `script_outro.txt`, `script.txt` or `narration.txt`, a transcript. Their words and their argument come
   first. Tighten; don't replace.

3. **Split the budget.** Bauhaus came out as intro 37, pictures 116,
   closing 63. Roughly **15% / 55% / 30%**.

4. **Write three blocks**, ready to paste:
   - **Intro**: for the camera window.
   - **Narration**: one paragraph per picture, in order, with a blank
     line between them. `-` for a picture with no words; `[5]` to jump.
     Put a picture's title in its paragraph only if it will be said.
   - **Closing**: for the camera window, recorded **after** the
     narration, so it plays last.

5. **Check it before showing it:**
   - count the words, and the estimated seconds;
   - every paragraph describes *its* picture;
   - no point is made twice;
   - facts are the user's. Don't add a date, a number or a name they
     didn't give. Say what you couldn't confirm from the image (on
     Bauhaus: whether picture 6 is really "Haus Anton").

6. **Write each block where its recording window opens it**, so nothing
   has to be pasted (Jacek's request, 2026-09-23):
   - Intro → `projects/NAME/script_intro.txt`
   - Narration → `projects/NAME/narration.txt`
   - Closing → `projects/NAME/script_outro.txt`

   Plain text only: no headings and no word counts inside these files,
   because the window shows every character on the prompter.
   **If one of these files already exists and is not empty, don't
   overwrite it.** It holds words the user typed or already recorded.
   Put that block in `write-to-fit_DATE.txt` instead, and say so.
   Always also write `projects/NAME/write-to-fit_DATE.txt`: all three
   blocks with a word count per block, as the record of what was
   planned.

7. **Show the table** (block, words, seconds) and the file path. After
   the user records, measure the real length and update the rate above.

## Never

- Go over the budget "because it's important". Offer what to cut
  instead.
- Invent facts to fill a picture. `-` is a good answer.
- Record, render or edit `film.yaml`. This skill ends at the text.
