# Code map — the places read again and again

Pointers, not copies. File, function, what it decides.

## Recording: intro, narration, closing (read 2026-09-19, -20, -23)
- `ffilm/guide.py` `_best_steps` — which step the menu offers first.
  `recording_doors` — the "record again" entries. `walk` — the menu screen
  and keys (M/N/F/C/Q). `so_far` — the "So far:" line.
- `ffilm/cli.py` `cmd_record` — `--intro` / `--closing` retakes;
  `_intro_and_closing` classifies takes; `_replace_takes` moves old takes to
  `media/_discarded/` and names new ones `0_rec_` (intro) / `close_rec_`
  (closing).
- `ffilm/scaffold.py` `place_takes` — takes before the narration open the
  film, after it close it; named `0_`/`close_` ones stay put.
- `ffilm/booth.py` `script_path` — which text the window opens with:
  `narration.txt`, `script_intro.txt`, `script_outro.txt`; older names
  in `PART_FILES`.
- `ffilm/kinds.py` — `STILL` (picture types), `is_recording`,
  `CLOSE_PREFIX`, `NUM_PREFIX`.

## Devices
- `ffilm/record.py` `list_devices`, `load_choice`, `save_choice`
  (`.devices.json`). Menu key M: `guide._pick_devices`.

Files use CRLF line endings: change them with the Edit tool.
