# Tech notes — one per library or tool

Read the note **before** fetching a library's documentation from the web.
Add to it **after** learning something the hard way. Short, dated, and only
what this project relies on.

Two things are saved here, always:

1. **Web documentation read** — a hook in `.claude/settings.json` reminds
   Claude after every web fetch or search. Save the call, the version, the
   trap; not the whole page.
2. **Code read again and again** — when the same function has to be found
   and read in two sessions (e.g. how the menu decides the next step), put
   a 5-line pointer here in `code-map.md`: file, function, what it decides.
   Reading 5 lines beats re-reading a 1,500-line file.

| Note | What it covers |
|---|---|
| [[ffmpeg]] | recording (dshow), the sound measurements, filter order |
| [[opencv]] | reading images on Windows, the 5.0 trap |
| [[pillow]] | which picture types the film reads, and which it does not |
| [[faster-whisper]] | captions, the optional `voice` extra |

Why notes and not a vector database: see the 2026-09-23 conversation —
at tens of notes, a file name finds the right one exactly. Add semantic
search (e.g. Obsidian's Smart Connections) when there are hundreds.
