"""The ducking compressor stops when its trigger stops. The trigger is the
speech, so a film that ends on a picture with nobody talking lost its
music at the last word: Happy Birthday Cherie Lorraine, 2026-09-24, silent
(-55.4 LUFS) from 48.5 s to 58.5 s under a 10 s closing card. Measured
alone: 20 s of music ducked under 5 s of speech came out 4.96 s long.

So the trigger is padded with silence to the length of the film."""
from ffilm.audio import duck_filters


def test_the_trigger_is_padded_to_the_whole_film():
    f = duck_filters("mus", "key", 68.5, 0.5)
    assert "[key]apad=whole_dur=68.500" in f


def test_the_compressor_listens_to_the_padded_trigger():
    f = duck_filters("mus", "key", 68.5, 0.5)
    pad = f.split(";")[0]
    padded = pad[pad.rindex("[") + 1:-1]
    assert f.split(";")[1].startswith(f"[mus][{padded}]sidechaincompress=")
    assert f.endswith("[ducked]")
