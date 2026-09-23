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
| one picture again (`record --voice --picture [N]`) | `pictureN_….wav` + `.picture.json` | over that picture only |
- A retake moves the old take to `media/_discarded/` only after the new
  one saved. A stopped narration is discarded; the menu comes back.
- A new whole narration also moves the older narrations and every
  picture retake aside (3855bb7).
- Picture retake: only that shot's `voice/in/out/note` and captions
  change; in/out = first word − 0.3 s to last word + 0.3 s. The
  `.picture.json` names the picture (the N is only its place that day),
  so `go --rewrite` / `init --force` keep it if it is newer than the
  narration (`scaffold.keep_retakes`). The text in the window is saved to
  `analysis/pictureN.txt`, never over `narration.txt`. Trial on a copy of
  Turn Heat, 2026-09-23: 17.7 s from take to captions; only s05 changed.
  **Not measured yet:** the level step between a retake and the
  narration around it (a real retake is a new sitting).
- A recording newer than film.yaml → menu's first step is
  `go --rewrite` (old edit kept as film.yaml.bak).

## Texts shown while recording
`script_intro.txt`, `narration.txt` (blank line = next picture),
`script_outro.txt`. Older names (`intro.txt`, `closing.txt`, `script.txt`)
are still read. The outro never opens on the intro's words.
`booth.script_path` / `booth.PART_FILES` decide.

## Where in the code
See [[code-map]].
