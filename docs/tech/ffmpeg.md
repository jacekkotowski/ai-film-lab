# ffmpeg

Found on the PATH by `ffilm/ffmpeg.py`. Not a Python package.

## Recording (Windows, dshow)
- Devices are listed by *failing* to open one:
  `ffmpeg -list_devices true -f dshow -i dummy`. Non-zero exit is normal.
- **dshow gives a webcam to one program only.** `booth.py` splits one
  ffmpeg's picture; never map the camera twice — the file starves.
- The chosen camera/mic is saved per machine in `.devices.json`.
  Change it: menu **M**, or `uv run film devices --mic "<name>"`.
  2026-09-23: a mic plugged in *after* the choice was saved is not picked
  up automatically — the laptop mic kept being used.
- The Elgato **Virtual** Camera records a frozen placeholder. Use the
  Facecam Pro.

## Measuring sound (never judge by ear here)
- Level: `ffmpeg -i f -af volumedetect -f null -` → mean/max dB.
- Loudness: `-af ebur128`.
- Sweep the **whole** take; two points are not a trend (decision 0003).

## Filter order
- `arnndn` goes **after** `speechnorm`; before it, ffmpeg hangs at the end
  of the stream (decision 0008).
- `sidechaincompress` stops when its **trigger** stops (20 s music, 5 s
  key -> 4.96 s out). The speech key is `apad`-ed to the film length
  (`audio.duck_filters`), or the music dies at the last word.

## Probing a file
`ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate:format=duration -of compact f`
