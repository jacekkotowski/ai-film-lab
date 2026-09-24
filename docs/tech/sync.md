# Sync — picture against sound

Read before any "the lips are out of sync" work. Add to it after.

## Current state (2026-09-23)
- **Cause, measured:** `film record` opens camera and microphone as two
  dshow inputs. The microphone starts **0.849 s** after the camera (test
  take with `-copyts`, real clock kept). Without `-copyts` each input is
  rebased to 0, so the voice played that much before the lips.
- **Fix:** `audio.sound_lag(src)` = picture length − sound length of a
  `rec_` take (both stop together on `q`); `audio.speech_specs` reads the
  sound that much later; `cli` caption step shifts lines by the same.
  Commit c802fcd. Slides narration is a separate wav — never shifted.
- **Proof on Turn Heat draft:** intro +40 ms (r 0.97), closing −80 ms
  (r 0.78); before −483 / −314 ms. Visible from ~80 ms.
- **Not measured:** that picture and sound really stop together.

## 2026-09-24 — two more faults from the same lost clock
- **The webcam's frame rate varies** (Frankfurt intro: 1423 frames in
  31.1 s; labelled 60, OpenCV says 44.72). The final picked frame =
  time × one rate: lips +0.47 s late at 2 s, −0.50 s early at 27 s.
  Fixed 646de5c: frames found by their own timestamps. Measured on the
  take: −0.017 s (one frame) everywhere. **Drafts hide this fault**
  (proxy re-timed to a steady rate) — sync must be checked on a FINAL.
- **Cut points were on the sound's clock** after c802fcd moved the
  sound: last word clipped 0.31/0.36 s. Fixed 2881ea5.
- Root, not done: recording keeps no real timing (both streams start at
  0, varying frame rate). Every stage reconstructs it.

## Wrong turns — do not repeat
- **Decision 0011 (2026-09-21) said "no sync fault".** It compared the
  film's sound with the take's sound — both carry the same fault, so
  they matched. **Always measure sound against PICTURE inside the take.**
- Blaming the 1.2 speed: speed is applied to picture and sound alike.
- Lip-motion correlation (mouth box, frame difference): r ≈ 0.01–0.2,
  noise. Don't re-run (0011 lists five variants).

## Snippets
Picture vs sound length in a take (the fault's signature):
```
ffprobe -v error -show_entries stream=codec_type,start_time,duration -of compact TAKE.mp4
```
Which stream really starts first (keeps the wall clock):
```
ffmpeg -f dshow -use_wallclock_as_timestamps 1 -t 6 -i "video=CAM" \
       -f dshow -use_wallclock_as_timestamps 1 -t 6 -i "audio=MIC" \
       -map 0:v -map 1:a -c:v libx264 -preset ultrafast -c:a aac -copyts t.mkv
ffprobe -v error -show_entries stream=codec_type,start_time -of compact t.mkv
```
Voice vs picture in a render: log-RMS envelope (10 ms bins) of the render
against the source take `atempo`-matched, cross-correlated around the
position the picture implies. Script kept in the 2026-09-23 session;
core: `env(x)=log(sqrt(mean(x[80-sample blocks]^2))+1e-4)` at 8 kHz.
