---
name: fit-to-length
description: Cut a finished film down to a length (a YouTube Short is 3:00) by dropping whole sentences and whole shots that say something twice, never by speeding up or splitting words. Use when the user says "make it a Short", "get it under 3 minutes", "compress to N seconds", or `film final` warns the film is too long for a Short.
---

# Fit to length: cut the repetition, not the words

`uv run film go --target N` already shortens photographs and drops
silent ones. It **never cuts anything spoken**, and in a narrated film
the speech *is* the length. Past that point, deciding what goes is a
judgement about meaning: which sentences say the same thing twice. That
judgement is this skill.

Done first on 2026-09-19, German Forgotten Bauhaus Hope: 281.8 s cut to
171.6 s in 8 cuts, with no word split. The numbers below come from that
cut.

## Steps

1. **Try the machine first.** If the film has silent photographs, run
   `uv run film go -p NAME --target 175` and check the new length. If
   that is enough, stop here.

2. **Measure, don't estimate.**
   - `uv run film check -p NAME` gives every shot's length. Their sum is
     the film's length; dissolves do not overlap.
   - `analysis/transcript.txt` gives every sentence, with its times.
   - Leave margin: aim for **about 172 s** for a 180 s limit.

3. **List the candidates**, cheapest first:
   - silence: a shot with no captions, where ffmpeg `volumedetect` says
     it is quiet (the Bauhaus s18 was −58.7 dB, against −25.6 dB for
     speech);
   - photographs with no words (`voice:` missing);
   - a sentence said twice: the intro and the closing often make the
     same point, and two pictures of the same place often describe the
     same thing;
   - after that, the weakest link in the argument. Say plainly that it
     is a judgement.

4. **Cut only at sentence ends and shot boundaries.** To end a clip
   early, find the pause after the last kept word with
   `silencedetect=noise=-38dB:d=0.2` and set `out:` inside that pause.
   Then remove any caption that now starts after the shot ends, and
   shorten a caption that runs past it.

5. **Propose, then wait.** One table: what is cut, the seconds it saves,
   why it can go, and the total that remains. Say which numbers were
   measured and which were reasoned. **Do not edit until the user says
   go.** It is their argument being cut.

6. **Before editing, make sure the current version is committed**
   (`git log -1 -- projects/NAME/film.yaml`), so `film undo` brings it
   back.

7. **Edit `film.yaml`:** delete the whole shot blocks, and change
   `out:` for the trimmed clips.
   - A talking clip that now follows a photograph gets no `dissolve:`;
     dissolves are only for joins inside one take.
   - Check that no two neighbouring shots now share a move family
     (`ffilm/moves.py` `FAMILY`).
   - Add a `note:` to each trimmed shot saying what was cut and why.

8. **`film check`** must say OK, and its total must match the proposal.
   Then `uv run film peek`. `film final` only when the user asks.

## Never

- Change `speed:` to save time. It changes the voice, and the pace was
  set to match the narration.
- Invent or shift `words:` timings.
- Cut inside a sentence to save two seconds. Pick a different sentence
  instead.
