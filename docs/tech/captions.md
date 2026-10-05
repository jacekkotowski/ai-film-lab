# Captions — words on screen

- Transcribed on this machine by [[faster-whisper]] (optional `voice`
  extra). Spelling and line breaks come from the text pasted when
  recording: `narration.txt`, `script_intro.txt`, `script_outro.txt`
  (`intro.txt`, `closing.txt`, `script.txt` in older projects).
- The English model misses German/Polish words, names, numbers → skill
  `fix-captions`; it keeps the script's spelling, never invents timings.
- A name heard with another spelling ("Kathrin Karsay" → "Catherine
  Carcey") can lose its WHOLE script line, not only the timing (What Is
  Love, 2026-09-28). Whisper `small` on a 9–17 s slice gave every word
  with times that agreed with the full-take times to within 0.04 s.
  So re-transcribing just the gap is a reliable way to place the line.
  The cause was the false-start rule. Since eec1145 a gap counts only
  for the heard words beyond the written ones it skipped, and a misheard
  written word takes the heard word's time (`voice._misheard`).
- Camera-take captions move with the sound-lag fix — see [[sync]].
- `film check` names unreadable captions (too short to read) and repeated
  ones; thresholds swept over 19 films — decision 0012.
- A caption shorter than its shot is fine; one cut by the next caption:
  the note "ends at X s, where the next caption begins".
- Whisper starts ~1 word in 10 inside the pause before it (SUMIFS tight
  narration: 30 of 300 words, 27 of 51 caption starts). Since 2026-10-05
  `voice.snap_to_pauses` moves such a start to the pause's end (pauses
  >= 0.2 s; 0.1 s also caught the gap before a "t"/"p" inside a word).
  Re-transcribing a slice does NOT fix number timing (157.55 still
  ~1.3 s early).
