"""
The shelf -- the music and the cover pictures that every film shares.

The promise being tested is a small one and it is the whole point: you
put a track in one folder, once, and every film you make from then on
has music without anybody typing anything. So the rules that matter are
about precedence (this film's own folder always wins) and about failing
quietly (an empty shelf, a missing shelf, a shelf full of rubbish -- none
of these may stop a film).
"""

from pathlib import Path

import pytest

from ffilm import library
from ffilm.spec import Film, find_music, headers, pretty_name, title_of


def track(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_bytes(b"ID3fake")
    return p


def film_yaml(project: Path, body: str = "") -> Path:
    """The smallest film that loads: one shot, one file that exists."""
    (project / "media").mkdir(parents=True, exist_ok=True)
    (project / "media" / "a.jpg").write_bytes(b"x")
    yml = project / "film.yaml"
    yml.write_text(
        body + "\nfps: 24\nshots:\n  - src: media/a.jpg\n    duration: 2.0\n",
        encoding="utf-8")
    return yml


# --------------------------------------------------------------------------
# Where the shelf is
# --------------------------------------------------------------------------

def test_the_shelf_sits_beside_the_toolkit_by_default(monkeypatch):
    monkeypatch.delenv("FFILM_LIBRARY", raising=False)
    assert library.root().name == "library"
    assert library.enabled()


def test_the_shelf_can_be_moved_somewhere_else(tmp_path, monkeypatch):
    """A synced folder, another drive. Nothing in the toolkit assumes
    the shelf is inside it."""
    monkeypatch.setenv("FFILM_LIBRARY", str(tmp_path / "elsewhere"))
    assert library.root() == tmp_path / "elsewhere"


def test_the_shelf_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("FFILM_LIBRARY", "")
    assert not library.enabled()
    assert library.music() is None
    assert library.backdrops() == []


def test_switching_it_off_creates_nothing(monkeypatch):
    """An off switch that still makes two folders is not an off switch --
    and with FFILM_LIBRARY empty, root() is the folder you are standing
    in, which is the last place to scatter music\\ and cover\\ into."""
    monkeypatch.setenv("FFILM_LIBRARY", "")
    assert library.ensure() is None


def test_making_the_shelf_leaves_an_explanation_on_it(shelf):
    library.ensure()
    readme = next(p for p in shelf.iterdir() if p.suffix == ".txt")
    assert "EVERY film" in readme.read_text(encoding="utf-8")


def test_making_the_shelf_twice_does_not_overwrite_your_notes(shelf):
    library.ensure()
    readme = next(p for p in shelf.iterdir() if p.suffix == ".txt")
    readme.write_text("my own words", encoding="utf-8")
    library.ensure()
    assert readme.read_text(encoding="utf-8") == "my own words"


# --------------------------------------------------------------------------
# The music
# --------------------------------------------------------------------------

def test_a_track_on_the_shelf_is_found(shelf):
    track(shelf / "music", "quiet.mp3")
    assert library.music().name == "quiet.mp3"


def test_the_first_track_alphabetically_wins(shelf):
    """So putting 01_ in front of one of them chooses between them, the
    same rule as everywhere else in the toolkit."""
    track(shelf / "music", "02_second.mp3")
    track(shelf / "music", "01_first.mp3")
    assert library.music().name == "01_first.mp3"


def test_a_stray_text_file_on_the_shelf_is_ignored(shelf):
    (shelf / "music" / "notes.txt").write_text("x", encoding="utf-8")
    assert library.music() is None


def test_a_missing_shelf_is_not_an_error(tmp_path, monkeypatch):
    """Every installation made before the shelf existed has no shelf."""
    monkeypatch.setenv("FFILM_LIBRARY", str(tmp_path / "never_made"))
    assert library.music() is None
    assert library.backdrop(wide=True) is None


# --------------------------------------------------------------------------
# Which music a film ends up with
# --------------------------------------------------------------------------

def test_a_film_with_no_music_of_its_own_takes_the_shelf(tmp_path, shelf):
    track(shelf / "music", "shared.mp3")
    found = find_music(tmp_path)
    assert Path(found).name == "shared.mp3"
    assert Path(found).is_absolute()      # it lives outside the project


def test_this_films_own_music_folder_wins(tmp_path, shelf):
    track(shelf / "music", "shared.mp3")
    track(tmp_path / "music", "mine.mp3")
    assert find_music(tmp_path) == "music/mine.mp3"


def test_a_films_own_track_is_recorded_relative_to_the_film(tmp_path, shelf):
    """So that the project folder can be zipped up, carried to another
    computer and still find its own music."""
    track(tmp_path / "music", "mine.mp3")
    assert not Path(find_music(tmp_path)).is_absolute()


def test_an_empty_music_folder_falls_through_to_the_shelf(tmp_path, shelf):
    """`film new` makes music/ for you, so an empty one is the normal
    state -- it must not read as "this film wants silence"."""
    (tmp_path / "music").mkdir()
    track(shelf / "music", "shared.mp3")
    assert Path(find_music(tmp_path)).name == "shared.mp3"


def test_loading_a_film_picks_the_shelf_up(tmp_path, shelf):
    """The end of the whole chain: one file dropped in one folder, and a
    film.yaml that says nothing about music has music."""
    track(shelf / "music", "shared.mp3")
    film = Film.load(film_yaml(tmp_path))
    assert Path(film.music).name == "shared.mp3"
    assert film.resolve(film.music).exists()


def test_music_named_in_film_yaml_beats_both(tmp_path, shelf):
    track(shelf / "music", "shared.mp3")
    track(tmp_path / "media", "chosen.mp3")
    film = Film.load(film_yaml(tmp_path, "music: media/chosen.mp3"))
    assert film.music == "media/chosen.mp3"


def test_with_nothing_anywhere_a_film_is_simply_quiet(tmp_path, shelf):
    assert Film.load(film_yaml(tmp_path)).music is None


# --------------------------------------------------------------------------
# What the film is called
# --------------------------------------------------------------------------

def test_a_film_is_called_after_its_folder(tmp_path):
    project = tmp_path / "late_evening_walk"
    project.mkdir()
    assert Film.load(film_yaml(project)).title == "Late Evening Walk"


def test_a_title_in_film_yaml_is_kept_exactly(tmp_path):
    """Capitalisation included. Somebody typed it."""
    film = Film.load(film_yaml(tmp_path, "title: a quiet word"))
    assert film.title == "a quiet word"


def test_pretty_names_leave_ordinary_words_alone():
    assert pretty_name("Zima nad morzem") == "Zima nad morzem"
    assert pretty_name("morning-walk") == "Morning Walk"
    assert pretty_name("") == ""


def test_the_folder_name_is_the_last_word_on_it(tmp_path):
    assert title_of(tmp_path) == pretty_name(tmp_path.name)


# --------------------------------------------------------------------------
# Reading a film.yaml without loading the film
# --------------------------------------------------------------------------

def test_headers_read_the_top_level_keys(tmp_path):
    yml = tmp_path / "film.yaml"
    yml.write_text("fps: 30\nresolution: [1080, 1920]\n", encoding="utf-8")
    assert headers(yml)["resolution"] == [1080, 1920]


def test_headers_do_not_care_whether_the_footage_exists(tmp_path):
    """The reason this exists: a thumbnail should still build for a film
    whose media is on a drive that is not plugged in."""
    yml = tmp_path / "film.yaml"
    yml.write_text("title: Away\nshots:\n  - src: D:/gone.jpg\n    duration: 1\n",
                   encoding="utf-8")
    assert headers(yml)["title"] == "Away"
    with pytest.raises(SystemExit):
        Film.load(yml)


def test_headers_of_a_file_that_is_not_there(tmp_path):
    assert headers(tmp_path / "nothing.yaml") == {}


def test_headers_of_a_file_being_hand_edited(tmp_path):
    """Halfway through typing, film.yaml is often not valid YAML. Nothing
    that merely wants to know the shape of the film may break on that."""
    yml = tmp_path / "film.yaml"
    yml.write_text("fps: [24\n", encoding="utf-8")
    assert headers(yml) == {}


def test_headers_of_a_file_that_is_not_a_mapping(tmp_path):
    yml = tmp_path / "film.yaml"
    yml.write_text("- just\n- a list\n", encoding="utf-8")
    assert headers(yml) == {}
