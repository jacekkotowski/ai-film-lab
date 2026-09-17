"""
scaffold.build always wrote `audio_offset: 0.0` for a narration track,
even when the film opens on a four-second title card. Measured on the
2026-09-17 scratch project (mixed_project.py): `init` put the narration
under the silent card, so the first four seconds of a 14s voiceover
played under nobody's name and no picture worth watching -- and the
scaffold's own comment on the card block says it is "a stillness before
the first person speaks", which a narration starting at 0.0 contradicts.

Numbers only here, except for the two ffmpeg-free image writes the
title card needs to exist at all -- see test_title_card.py, which this
borrows its fixtures from.
"""

import json
from pathlib import Path

from PIL import Image

from ffilm import scaffold
from ffilm.scaffold import SHORT_TITLE_CARD_SECONDS, TITLE_CARD_SECONDS


def picture(path: Path, w: int, h: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (70, 90, 110)).save(path)
    return path


def stocked(shelf: Path) -> None:
    picture(shelf / "cover" / "a_wide.jpg", 1600, 900)
    picture(shelf / "cover" / "b_tall.jpg", 900, 1600)


def project_with_audio(tmp_path: Path, vertical: bool = False) -> Path:
    p = tmp_path / "narrated"
    media = p / "media"
    media.mkdir(parents=True)
    (p / "analysis").mkdir()
    picture(media / "01_harbour.jpg", 1200, 800)
    (media / "voiceover.wav").write_bytes(b"")     # only the suffix matters
    if vertical:
        (p / ".vertical").write_text("", encoding="utf-8")
    manifest = {"media": [{"path": "media/01_harbour.jpg", "kind": "still",
                           "focus": [0.5, 0.5]}]}
    (p / "analysis" / "manifest.json").write_text(json.dumps(manifest),
                                                   encoding="utf-8")
    return p


def test_a_narration_waits_for_the_widescreen_card(tmp_path, shelf):
    stocked(shelf)
    text = scaffold.build(project_with_audio(tmp_path))
    assert f"audio_offset: {TITLE_CARD_SECONDS:.1f}" in text


def test_a_narration_waits_for_the_shorter_vertical_card(tmp_path, shelf):
    stocked(shelf)
    text = scaffold.build(project_with_audio(tmp_path, vertical=True))
    assert f"audio_offset: {SHORT_TITLE_CARD_SECONDS:.1f}" in text
    assert f"audio_offset: {TITLE_CARD_SECONDS:.1f}" not in text


def test_with_no_card_the_narration_starts_at_zero(tmp_path, shelf):
    """No picture on the shelf, so title_card_block has nothing to build
    -- and the narration has nothing to wait for."""
    text = scaffold.build(project_with_audio(tmp_path))
    assert "audio_offset: 0.0" in text
