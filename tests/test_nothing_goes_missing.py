"""
The ways material used to disappear without a word.

Every test here is a file that was dropped into media/ in good faith and
then was not in the film, with nothing on screen to say why. That is the
worst thing this toolkit can do, and each of these is one route to it.
"""

import numpy as np
import pytest

from ffilm import pix
from ffilm.checks import framing_notes, unused_media
from ffilm.ingest import analysis_keys, in_capture_order
from ffilm.spec import Film, Shot


# --------------------------------------------------------------------------
# A name OpenCV cannot open
# --------------------------------------------------------------------------


ACCENTED = "zdjęcie_Kołobrzeg_ąćęłńóśźż"


def test_a_picture_with_an_accented_name_round_trips(tmp_path):
    """cv2.imread/imwrite pass the path through the machine's ANSI
    codepage, so on Windows this file does not open at all -- and says
    so by returning None, which is indistinguishable from corrupt."""
    folder = tmp_path / "Zima nad morzem"
    folder.mkdir()
    p = folder / f"{ACCENTED}.jpg"
    img = np.full((40, 60, 3), 128, np.uint8)

    assert pix.imwrite(p, img) is True
    assert p.exists() and p.stat().st_size > 0
    back = pix.imread(p)
    assert back is not None
    assert back.shape == (40, 60, 3)


def test_a_missing_file_reads_as_none_not_an_exception(tmp_path):
    assert pix.imread(tmp_path / "not_here.jpg") is None


def test_an_empty_file_reads_as_none(tmp_path):
    p = tmp_path / "empty.jpg"
    p.write_bytes(b"")
    assert pix.imread(p) is None


def test_a_write_into_a_folder_that_does_not_exist_yet_works(tmp_path):
    p = tmp_path / "made" / "up" / "path.jpg"
    assert pix.imwrite(p, np.zeros((8, 8, 3), np.uint8)) is True
    assert p.exists()


def test_png_and_jpg_both_go_through_their_own_codec(tmp_path):
    img = np.full((12, 12, 3), 200, np.uint8)
    for ext in (".jpg", ".png"):
        p = tmp_path / f"pic{ext}"
        assert pix.imwrite(p, img) is True
        assert pix.imread(p) is not None


# --------------------------------------------------------------------------
# Two files with the same name in different folders
# --------------------------------------------------------------------------


def test_a_unique_stem_keeps_its_own_name():
    """Every project that already exists is flat and unique, and must not
    be re-analysed for the sake of this."""
    keys = analysis_keys(["media/rec_1.mp4", "media/harbour.jpg"])
    assert keys["media/rec_1.mp4"] == "rec_1"
    assert keys["media/harbour.jpg"] == "harbour"


def test_the_same_stem_in_two_folders_gets_two_keys():
    """IMG_0042 appears in every folder on a camera card. Both used to
    share one proxy, one cuts file and one set of thumbnails."""
    keys = analysis_keys(["media/dzien1/IMG_0042.MOV",
                          "media/dzien2/IMG_0042.MOV"])
    assert len(set(keys.values())) == 2
    assert all(k.startswith("IMG_0042") for k in keys.values())


def test_the_same_stem_with_two_extensions_gets_two_keys():
    """IMG_0042.HEIC and IMG_0042.JPG off the same phone."""
    keys = analysis_keys(["media/IMG_0042.HEIC", "media/IMG_0042.JPG"])
    assert len(set(keys.values())) == 2


def test_keys_are_stable_between_runs():
    rels = ["media/a/x.mp4", "media/b/x.mp4", "media/y.jpg"]
    assert analysis_keys(rels) == analysis_keys(list(reversed(rels)))


def test_keys_are_safe_as_filenames():
    keys = analysis_keys(["media/holiday 2026/IMG_1.jpg",
                          "media/holiday 2027/IMG_1.jpg"])
    for k in keys.values():
        assert "/" not in k and "\\" not in k


# --------------------------------------------------------------------------
# What order were they taken in?
# --------------------------------------------------------------------------


def paths(*names):
    from pathlib import Path
    return [Path(n) for n in names]


def test_chronological_when_every_file_says():
    a, b, c = paths("media/DSC_9.jpg", "media/IMG_1.jpg", "media/PXL_5.jpg")
    when = {a: 300.0, b: 100.0, c: 200.0}
    assert in_capture_order([a, b, c], when) == [b, c, a]


def test_alphabetical_when_even_one_file_does_not_say():
    """A part-timed set sorted by time dumps the untimed file somewhere
    arbitrary, which is a worse answer than the filenames and a much
    harder one to argue with."""
    a, b, c = paths("media/a.jpg", "media/b.mp4", "media/c.jpg")
    when = {a: 300.0, b: None, c: 100.0}
    assert in_capture_order([a, b, c], when) == [a, b, c]


def test_no_files_at_all_is_not_a_crash():
    assert in_capture_order([], {}) == []


# --------------------------------------------------------------------------
# A file that is in media/ and in no shot
# --------------------------------------------------------------------------


def film_with(tmp_path, srcs):
    film = Film(root=tmp_path)
    film.shots = [Shot(src=s, id=f"s{i:02d}") for i, s in enumerate(srcs, 1)]
    return film


def test_a_photograph_no_shot_uses_is_named(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    for name in ("used.jpg", "forgotten.jpg"):
        (media / name).write_bytes(b"x")
    missing = unused_media(tmp_path, film_with(tmp_path, ["media/used.jpg"]))
    assert missing == ["media/forgotten.jpg"]


def test_a_shot_pointing_at_a_proxy_still_counts_the_original(tmp_path):
    """peek and draft swap in a 480p stand-in, and the original must not
    then look unused."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "clip.mov").write_bytes(b"x")
    film = film_with(tmp_path, ["analysis/proxies/clip.mp4"])
    assert unused_media(tmp_path, film) == []


def test_discarded_and_unreadable_takes_are_not_reported_as_missing(tmp_path):
    """They are set aside on purpose. Listing them as forgotten would
    make the warning noise, and a warning that is noise gets ignored."""
    media = tmp_path / "media"
    (media / "_discarded").mkdir(parents=True)
    (media / "_unreadable").mkdir(parents=True)
    (media / "_discarded" / "fluffed.mp4").write_bytes(b"x")
    (media / "_unreadable" / "broken.mp4").write_bytes(b"x")
    (media / "good.jpg").write_bytes(b"x")
    film = film_with(tmp_path, ["media/good.jpg"])
    assert unused_media(tmp_path, film) == []


def test_things_that_are_not_media_are_not_reported(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "notes.txt").write_bytes(b"x")
    (media / "good.jpg").write_bytes(b"x")
    film = film_with(tmp_path, ["media/good.jpg"])
    assert unused_media(tmp_path, film) == []


def test_a_film_using_everything_reports_nothing(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "a.jpg").write_bytes(b"x")
    (media / "b.jpg").write_bytes(b"x")
    film = film_with(tmp_path, ["media/a.jpg", "media/b.jpg"])
    assert unused_media(tmp_path, film) == []


# --------------------------------------------------------------------------
# A wide clip losing its subject to a tall frame
# --------------------------------------------------------------------------


def test_a_widescreen_film_is_never_told_about_cropping():
    """The suggestion is about a wide picture in a TALL frame."""
    film = Film(width=1920, height=1080)
    film.shots = [Shot(src="media/a.mp4", kind="video", focus=(0.05, 0.5))]
    assert framing_notes(film) == []


def test_a_shot_already_set_to_blur_is_not_nagged():
    film = Film(width=1080, height=1920, fill="blur")
    film.shots = [Shot(src="media/a.mp4", kind="video", focus=(0.05, 0.5))]
    assert framing_notes(film) == []


def test_stills_are_not_nagged():
    """A photograph usually has room to lose. A face does not."""
    film = Film(width=1080, height=1920)
    film.shots = [Shot(src="media/a.jpg", kind="still", focus=(0.02, 0.5))]
    assert framing_notes(film) == []
