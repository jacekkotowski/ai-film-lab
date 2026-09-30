"""A camera take keeps its last syllable.

GAM Curves Explain Data, 2026-09-30: the intro ended on "relationshi-".
The microphone was left at its default buffer, which hands sound over in
chunks of about half a second. SPACE stops ffmpeg, and the chunk still
filling is lost: 0.27-0.90 s off the end of every take that day. Hidden
while a take ended in silence; the syllable went when SPACE came soon
after the last word.

Measured on the Facecam Pro + Samson, `-copyts`, 5 s takes, `q` to stop:
default buffer, sound starts +0.72 s (stamped a chunk late); 50 ms, sound
starts +0.28 s and ends +0.003 / +0.012 s after the picture.
"""
from pathlib import Path

from ffilm.record import MIC_BUFFER_MS, record_command


def audio_input(c: list[str]) -> list[str]:
    """The flags of the microphone's input: from its `-f` to its `-i`."""
    i = next(n for n, x in enumerate(c) if x.startswith("audio="))
    start = max(n for n in range(i) if c[n] == "-f")
    return c[start:i]


def test_the_microphone_hands_over_sound_in_small_pieces():
    c = record_command(Path("take.mp4"), "Cam", "Mic")
    flags = audio_input(c)
    assert "-audio_buffer_size" in flags
    assert int(flags[flags.index("-audio_buffer_size") + 1]) <= 50


def test_a_voiceover_keeps_its_last_syllable_too():
    flags = audio_input(record_command(Path("v.wav"), None, "Mic"))
    assert flags[flags.index("-audio_buffer_size") + 1] == str(MIC_BUFFER_MS)


def test_the_camera_is_not_given_an_audio_flag():
    c = record_command(Path("take.mp4"), "Cam", "Mic")
    video_part = c[:c.index("video=Cam")]
    assert "-audio_buffer_size" not in video_part
