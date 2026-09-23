# faster-whisper — captions

- **Optional extra**, not one of the four core packages:
  `uv sync --extra voice` (~100 MB model, fetched once). Without it,
  captions simply don't happen; the menu offers the install.
- Runs on this machine; nothing is sent anywhere.
- The English transcriber misses German/Polish words, names and numbers:
  the `fix-captions` skill places those from the measured speech and keeps
  the script's spelling.
- Captions take their spelling from the text you pasted when recording:
  `narration.txt` (pictures), `intro.txt` / `closing.txt` (camera, since
  2026-09-23), `script.txt` (older projects).
