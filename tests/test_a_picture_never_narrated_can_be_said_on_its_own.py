"""A picture nobody has narrated yet can still be said on its own.

Found 2026-10-02 on Excel Time Logic: the whole narration was silent
where pictures 6 and 7 were cued, and `record --voice --picture 6` said
"out of range" -- the list of pictures held only shots that already had
a voice, 5 of the 7. A picture with no words had no way to get any
short of reading all seven again.

A photograph from media/ counts as a picture whether or not it has a
voice yet. The opening card (analysis/title.jpg) is not one.
"""
from ffilm import retakes
from ffilm.spec import Film

FILM = """\
shots:

  - id: s00
    src: analysis/title.jpg
    duration: 2.0

  - id: s01
    src: media/1_oil.jpg
    voice: media/picture1_x.wav
    in: "00:00.40"
    out: "00:12.60"
    move: tilt_up

  - id: s02
    src: media/2_thermo.jpg
    duration: 4.5
    move: columns
    focus: [0.46, 0.31]

  - id: s03
    src: media/3_chart.jpg
    duration: 4.5
    move: columns
"""


def _film(tmp_path):
    (tmp_path / "media").mkdir(exist_ok=True)
    (tmp_path / "analysis").mkdir(exist_ok=True)
    for name in ("media/1_oil.jpg", "media/2_thermo.jpg", "media/3_chart.jpg",
                 "media/picture1_x.wav", "media/picture2_y.wav",
                 "analysis/title.jpg"):
        (tmp_path / name).write_bytes(b"")
    p = tmp_path / "film.yaml"
    p.write_text(FILM, encoding="utf-8")
    return Film.load(p)


def test_a_photograph_without_words_is_a_picture_but_the_title_card_is_not(
        tmp_path):
    shots = retakes.picture_shots(_film(tmp_path))
    assert [s.id for s in shots] == ["s01", "s02", "s03"]


def test_the_menu_offers_it_by_name(tmp_path):
    menu = retakes.picture_menu(_film(tmp_path))
    assert [line.split()[:2] for line in menu] == [
        ["1", "1_oil.jpg"], ["2", "2_thermo.jpg"], ["3", "3_chart.jpg"]]


def test_a_new_take_gives_it_a_voice_and_keeps_its_move(tmp_path):
    film = _film(tmp_path)
    cut = retakes.retake_cut(film, 2, "media/picture2_y.wav", 0.3, 9.1)
    text = retakes.retake_text(FILM, cut, [])
    assert "voice: media/picture2_y.wav" in text
    assert 'in: "00:00.30"' in text and 'out: "00:09.10"' in text
    assert "move: columns" in text and "focus: [0.46, 0.31]" in text
    s02 = text.split("id: s02")[1].split("id: s03")[0]
    assert "duration" not in s02                 # the take sets the length
    assert text.count("voice:") == 2             # s01's and the new one
