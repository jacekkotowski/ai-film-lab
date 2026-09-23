"""A new narration puts the old ones aside.

The film uses only the newest narration (kinds.pick_narration). The
older ones stayed in media/ anyway: Turn Heat Into Images had six
voiceover takes there on 2026-09-23, 139 MB, five of them unused and
all of them looking alike. Aside means media/_discarded/, never deleted.
"""
from pathlib import Path

from ffilm import kinds

M = Path("media")


def test_only_the_new_narration_stays():
    files = [M / "voiceover_20260923-105420.wav",
             M / "voiceover_20260923-123826.wav"]
    assert kinds.older_narrations(files, files[1]) == [files[0]]


def test_the_cues_go_with_their_take():
    files = [M / "voiceover_20260923-105420.wav",
             M / "voiceover_20260923-105420.cues.json",
             M / "voiceover_20260923-123826.wav",
             M / "voiceover_20260923-123826.cues.json"]
    assert sorted(kinds.older_narrations(files, files[2])) == sorted(files[:2])


def test_music_photos_and_camera_takes_are_never_touched():
    files = [M / "song.mp3", M / "1_oil.jpg", M / "rec_20260923-123013.mp4",
             M / "0_rec_20260923-123013.mp4",
             M / "voiceover_20260923-123826.wav"]
    assert kinds.older_narrations(files, files[-1]) == []
