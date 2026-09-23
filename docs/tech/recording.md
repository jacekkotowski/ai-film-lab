# Recording — camera, microphone, takes, texts

## Devices
- Saved per machine in `.devices.json`. Change: menu **M**, or
  `uv run film devices --mic "<name>"`. A mic plugged in after the choice
  was saved is NOT picked up (2026-09-23: takes went to the laptop mic).
- Facecam Pro says 60 fps, delivers ~43, unevenly (measured 2026-09-23).
- Elgato Virtual Camera records a frozen placeholder — never use it.
- A frozen, quiet or hissy take is usually the device/room: decision 0004.

## Takes and where they play (commits 576fdaf, 4a2b029, 50cd700)
| Take | Name | Plays |
|---|---|---|
| intro (menu, `record --intro`) | `rec_…`, or `0_rec_…` if a narration exists | first |
| narration (`record --voice`) | `voiceover_….wav` + `.cues.json` | over the pictures; newest wins |
| closing (`record --closing`) | `close_rec_…` | last, always |
- A retake moves the old take to `media/_discarded/` only after the new
  one saved. A stopped narration is discarded; the menu comes back.
- A recording newer than film.yaml → menu's first step is
  `go --rewrite` (old edit kept as film.yaml.bak).

## Texts shown while recording
`intro.txt`, `narration.txt` (blank line = next picture), `closing.txt`;
`script.txt` for older projects. `booth.script_path` decides.

## Where in the code
See [[code-map]].
