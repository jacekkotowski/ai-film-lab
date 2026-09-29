"""
The final film says where every shot is.

`film final` writes out/final.timeline.json beside the video, so another
tool -- a 3D flight through the slides, a subtitle file, a chapter list --
can find each shot in the mp4 without re-deriving this toolkit's rules.

The times are counted in FRAMES, the way the renderer counts them. Summed
as seconds they drift: 5.03s at 24fps is 121 frames, 5.0417s on screen,
and the error grows with every shot (see spec.frames_for).
"""

import hashlib
import json
from pathlib import Path

from ffilm.spec import Caption, Film, Shot, frames_for
from ffilm.timeline import export, path_for, write

CARD = "analysis/title.jpg"


def still(src, dur=5.0, sid="", **kw) -> Shot:
    return Shot(src=src, duration=dur, kind="still", id=sid, **kw)


def take(src, dur=5.0, sid="", **kw) -> Shot:
    return Shot(src=src, duration=dur, kind="video", id=sid, **kw)


def slide(src, dur=5.0, sid="", **kw) -> Shot:
    return still(src, dur, sid, voice="media/voiceover_1.wav", **kw)


def lesson() -> Film:
    """The shape of The Trade Behind War: card, two intro takes, slides,
    a closing take."""
    return Film(fps=24, title="The Trade Behind War", shots=[
        still(CARD, 2.0, "s00"),
        take("media/rec_20260923-172642.mp4", 12.6, "s01", captions=[
            Caption(text="Poland's prime minister says", at=0.2, dur=4.5)]),
        take("media/rec_20260923-172642.mp4", 12.3, "s02"),
        slide("media/1german_exports_english.png", 20.6, "s03"),
        slide("media/2french_exports_english.png", 18.4, "s04"),
        take("media/close_rec_20260923-174641.mp4", 12.6, "s05"),
    ])


def shots(film) -> list[dict]:
    return export(film, CARD, "final.mp4")["shots"]


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------

def test_the_first_shot_starts_at_frame_zero():
    assert shots(lesson())[0]["start_frame"] == 0


def test_each_shot_starts_on_the_frame_the_last_one_ended():
    s = shots(lesson())
    for before, after in zip(s, s[1:]):
        assert after["start_frame"] == before["end_frame"]


def test_the_frames_add_up_to_what_the_renderer_draws():
    film = lesson()
    total = sum(frames_for(s.duration, film.fps) for s in film.shots)
    out = export(film, CARD, "final.mp4")
    assert out["frames"] == total
    assert out["shots"][-1]["end_frame"] == total


def test_seconds_are_frames_over_fps_not_summed_seconds():
    """5.03 + 5.03 summed is 10.06s. The film is 121 + 121 frames."""
    film = Film(fps=24, shots=[still("media/a.jpg", 5.03),
                               still("media/b.jpg", 5.03)])
    s = shots(film)
    assert s[1]["start_frame"] == 121
    assert s[1]["start"] == round(121 / 24, 3)
    assert s[1]["end_frame"] == 242


# --------------------------------------------------------------------------
# What each shot is for
# --------------------------------------------------------------------------

def test_each_shot_has_its_role():
    assert [s["role"] for s in shots(lesson())] == [
        "title", "intro", "intro", "slide", "slide", "closing"]


def test_with_no_narrated_pictures_a_take_is_only_a_clip():
    film = Film(shots=[still(CARD, 2.0), take("media/rec_20260905-1.mp4")])
    assert [s["role"] for s in shots(film)] == ["title", "clip"]


def test_a_take_between_two_slides_is_a_clip():
    film = Film(shots=[slide("media/a.png"), take("media/rec_1.mp4"),
                       slide("media/b.png")])
    assert shots(film)[1]["role"] == "clip"


def test_a_picture_with_no_words_is_a_clip():
    film = Film(shots=[still("media/harbour.jpg")])
    assert shots(film)[0]["role"] == "clip"


# --------------------------------------------------------------------------
# Titles
# --------------------------------------------------------------------------

def test_the_card_carries_the_films_title():
    assert shots(lesson())[0]["title"] == "The Trade Behind War"


def test_a_picture_is_named_by_its_file_without_the_order_number():
    assert shots(lesson())[3]["title"] == "German Exports English"


def test_a_take_is_named_by_its_first_line_not_its_date():
    assert shots(lesson())[1]["title"] == "Poland's prime minister says"


def test_a_take_with_nothing_said_is_named_by_its_role():
    s = shots(lesson())
    assert s[2]["title"] == "Intro"
    assert s[5]["title"] == "Closing"


def test_a_name_typed_with_spaces_is_kept_as_typed():
    film = Film(shots=[still("media/2declaration of love.jpg")])
    assert shots(film)[0]["title"] == "declaration of love"


# --------------------------------------------------------------------------
# Words, and the keys to everything else
# --------------------------------------------------------------------------

def test_captions_are_on_the_films_clock():
    c = shots(lesson())[1]["captions"][0]
    start = 48 / 24                                   # s00 is 2.0s = 48 frames
    assert c["start"] == round(start + 0.2, 3)
    assert c["end"] == round(start + 0.2 + 4.5, 3)


def test_a_caption_trimmed_to_nothing_is_left_out():
    film = Film(shots=[take("media/rec_1.mp4", captions=[
        Caption(text="gone", at=6.0, dur=0.0)])])
    assert shots(film)[0]["captions"] == []


def test_a_shot_keeps_the_keys_to_film_yaml_and_the_manifest():
    s = shots(lesson())[3]
    assert s["id"] == "s03"
    assert s["src"] == "media/1german_exports_english.png"
    assert s["voice"] == "media/voiceover_1.wav"


def test_the_film_says_its_own_shape():
    out = export(lesson(), CARD, "final.mp4")
    assert (out["version"], out["video"], out["fps"]) == (1, "final.mp4", 24)
    assert (out["width"], out["height"]) == (1920, 1080)


# --------------------------------------------------------------------------
# On disk
# --------------------------------------------------------------------------

def test_it_is_written_beside_the_video_it_describes(tmp_path):
    video = tmp_path / "out" / "final.mp4"
    video.parent.mkdir()
    out = write(lesson(), video, CARD)
    assert out == path_for(video) == tmp_path / "out" / "final.timeline.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["shots"][3]["title"] == "German Exports English"
    assert not list(video.parent.glob("*.part"))


# --------------------------------------------------------------------------
# The hand-off to the next stage (ai-3d-studio reads this file and nothing
# else of ours -- docs/decisions/0014)
# --------------------------------------------------------------------------

def test_the_film_has_one_name_in_both_stages():
    film = lesson()
    film.root = Path("projects/It Reads Us - We Can't Read It")
    assert export(film, CARD, "final.mp4")["slug"] == "it-reads-us-we-can-t-read-it"


def test_a_polish_l_in_the_name_is_kept_as_an_l():
    film = lesson()
    film.root = Path("projects/Frankfurt School vs Kołakowski")
    assert export(film, CARD, "final.mp4")["slug"] == "frankfurt-school-vs-kolakowski"


def test_the_video_is_fingerprinted_so_a_later_stage_sees_a_new_render(tmp_path):
    video = tmp_path / "out" / "final.mp4"
    video.parent.mkdir()
    video.write_bytes(b"first render")
    first = json.loads(write(lesson(), video, CARD).read_text(encoding="utf-8"))
    assert first["video_sha256"] == hashlib.sha256(b"first render").hexdigest()
    video.write_bytes(b"second render")
    second = json.loads(write(lesson(), video, CARD).read_text(encoding="utf-8"))
    assert second["video_sha256"] != first["video_sha256"]


def test_no_video_means_no_fingerprint_not_a_lost_render(tmp_path):
    video = tmp_path / "out" / "final.mp4"
    video.parent.mkdir()
    data = json.loads(write(lesson(), video, CARD).read_text(encoding="utf-8"))
    assert data["video_sha256"] is None


def test_the_keys_the_next_stage_reads_are_all_there():
    """ai-3d-studio's film_to_stops.py and fly.py read exactly these. Rename
    or drop one and the flight breaks with no warning here -- so bump
    VERSION instead."""
    out = export(lesson(), CARD, "final.mp4")
    assert {"version", "slug", "video", "video_sha256", "title", "fps",
            "width", "height", "frames", "shots"} <= out.keys()
    assert {"role", "kind", "src", "title", "start_frame", "end_frame"} <= out["shots"][0].keys()
