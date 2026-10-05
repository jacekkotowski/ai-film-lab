"""
2026-09-29, "It Reads Us - We Can't Read It": the intro was recorded
again, which moves the old take to media/_discarded/. film.yaml still
named the old take until the film is built again -- and every recording
of the pictures (all of them, or ONE) loaded film.yaml, found the file
missing, and refused to start:

    film.yaml has problems:
      - [s01] file not found: ...\\media\\rec_20260929-125904.mp4

Recording over a picture only needs the list of pictures. A missing
intro is the render's problem, and the render still refuses it.
"""

from pathlib import Path

import pytest

from ffilm import retakes
from ffilm.spec import Film

YAML = """\
fps: 24
resolution: [1080, 1920]
shots:
  - id: s01
    src: media/rec_old_intro.mp4
    duration: 5.0
  - id: s02
    src: media/1_photo.jpg
    duration: 5.0
    voice: media/voiceover_1.wav
    in: 0.0
    out: 5.0
    captions:
      - text: "The first words."
        at: 0.0
        dur: 2.0
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "1_photo.jpg").write_bytes(b"x")
    (tmp_path / "media" / "voiceover_1.wav").write_bytes(b"x")
    (tmp_path / "film.yaml").write_text(YAML, encoding="utf-8")
    return tmp_path / "film.yaml"


def test_the_pictures_can_be_listed_while_the_old_intro_is_gone(tmp_path):
    film = Film.load(_project(tmp_path), check_files=False)
    menu = retakes.picture_menu(film)
    assert len(menu) == 1 and "1_photo.jpg" in menu[0]


def test_the_render_still_refuses_a_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="file not found"):
        Film.load(_project(tmp_path))
