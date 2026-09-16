# models/ — fetched once, checked, never committed

The model files the toolkit needs live here, in this visible folder, and
nowhere else. Git ignores everything in this folder except this README,
and `film pack` carries only this README.

**Nothing has to be done by hand on a new computer.** The first time a
film needs a model, it is downloaded, its SHA-256 is checked against the
number below, and only then is it saved here. To fetch them all up front:

```
uv run film models
```

`uv run film doctor` says which are here. Without a network a film still
renders: the bokeh or the voice cleaning that needs the missing file is
left out, and the render says so.

The list that actually runs is `CATALOGUE` in `ffilm/models.py`; a test
checks that this table agrees with it.

| File | Size (bytes) | SHA-256 | Source | Used for | Licence |
|---|---:|---|---|---|---|
| `selfie_segmenter_landscape.tflite` | 250177 | `490e9ea734313e0de10fa0cd9e3c6133e36ea4db2b7a49bde9ef019f72796b8e` | https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite | bokeh: finds you in the frame (docs/decisions/0006) | Google MediaPipe; licence not yet confirmed from the model card |
| `sh.rnnn` | 297646 | `70bb6685eb0c2a1d18e2918dca3fbfbd39317010b1802eb1b6ea73a92f3fdec0` | https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn | voice: takes the room out from under your words (docs/decisions/0008) | The collection's README: the models are not creative work and not subject to copyright |

## Measured, not used

These were downloaded to compare, and nothing in `ffilm/` uses them. They
are not fetched on a new computer.

| File | Size (bytes) | SHA-256 | Source | Why not |
|---|---:|---|---|---|
| `human_segmentation_pphumanseg_2023mar.onnx` | 6163938 | `552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24` | https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg | kept a hanger sharp as a "person" (0006) |
| `bd.rnnn` | 299693 | `ae3f7411e1e6a884f839a4a145c394408398f09854dbc1216ee02faafc98a17b` | https://raw.githubusercontent.com/GregorR/rnnoise-models/master/beguiling-drafter-2018-08-30/bd.rnnn | cost 1.8 dB of consonants, and one ffmpeg run failed (0008); deleted |
