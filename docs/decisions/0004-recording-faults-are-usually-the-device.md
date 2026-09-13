# 0004 — Why does a recording come out frozen, quiet or hissy?

**Status:** settled 2026-09-12  ·  **Code:** `ffilm/record.py`, `ffilm/booth.py`

## The question
Three recording faults were each first suspected to be bugs in `ffilm/`.
None of them was.

## 1. The take plays back as a still image
Some virtual camera drivers (a webcam vendor's "Virtual Camera") are
listed *first* among the devices, and when their companion app isn't
actively feeding them they deliver a **frozen placeholder frame**. That
records as a flawless take and plays back as a photograph.

- **How to tell:** per-frame mean brightness. Identical values mean frozen;
  small fluctuations mean a live sensor.
- **Decision:** devices are discovered and chosen per machine
  (`.devices.json`), never hardcoded. Pick the physical camera.

## 2. Every take that day is ~17 dB too quiet
Conferencing apps with "automatically adjust microphone volume" (Zoom's
setting drives the *OS* slider) moved the Windows capture level from 80 %
to 55 %. The signal and the noise floor dropped together.

- **How to tell:** the voice and the room drop by the same amount.
- **Fix:** check the level before a session. `control mmsys.cpl,,1` opens
  the Recording tab.
- Peaks at 0 to +0.5 dBFS were **not** clipping: `astats` flat factor was
  0.00 on every take.

## 3. "Just turn the mic down to lose the hiss"
**It doesn't work.** Gain lowers the voice and the room equally, so their
ratio is unchanged. Then the take is normalised back to −20 LUFS, which
brings the room back up with it. A quieter take is strictly worse, because
denoising a quiet take eats consonants (see a40e16f).

What raises the voice-to-room ratio is **getting closer to the mic** (the
voice obeys the inverse-square law; the room doesn't) or switching off
whatever makes the noise. Measured takes are ~25 dB signal-to-noise; 40+
is normal at 30 cm.

## Reopen it only if
A fault reproduces with a known-good physical camera, the mic level
verified, and nothing else using the device.
