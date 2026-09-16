"""
Captions go INTO film.yaml without taking the rest of it with them.

This used to be `yaml.safe_load` then `yaml.safe_dump`, which is correct
YAML and deletes every comment in the file, because comments are not
data. `film go` captions on its own, so the explanatory header that
`film init` writes -- the one that says what every number means -- was
gone before anybody had opened the file once. Six of the eight films on
the machine this was written on had no comments left in them at all.

Every test here is one thing that must survive being captioned.
"""

import pytest

from ffilm.scaffold import add_captions
from ffilm.spec import Caption

SCAFFOLDED = """\
# Written by `film init`. Everything here is a starting point.
# Change the numbers. That is what this file is for.

fps: 24
resolution: [1080, 1920]   # vertical, for YouTube Shorts
music_volume: 0.6      # the level when nobody is talking

look:
  preset: old_film
  glow: 0.25

shots:

  - id: s00
    src: analysis/title.jpg
    duration: 4.0
    move: static
    note: "the opening card"

  - id: s01
    src: media/rec_1.mp4
    in: "00:00.00"
    out: "00:07.41"
    speed: 1.2
    move: static
    amount: 0.6
    focus: [0.549, 0.402]
    note: "kept whole -- there is sound on this one"

  - id: s02
    src: media/harbour.jpg
    duration: 4.5
    move: drift_left
    focus: [0.500, 0.500]

# 3 shots, about 16 seconds.
"""


def cap(text, at=1.0, dur=2.0):
    return Caption(text=text, at=at, dur=dur, pos="lower_third")


def load(text):
    import yaml
    return yaml.safe_load(text)


def test_every_comment_survives():
    """The whole reason this function exists."""
    out = add_captions(SCAFFOLDED, {"s01": [cap("hello")]})
    for line in SCAFFOLDED.splitlines():
        if line.strip().startswith("#"):
            assert line in out, f"lost a comment: {line}"
    assert "# vertical, for YouTube Shorts" in out
    assert "# the level when nobody is talking" in out


def test_the_caption_lands_on_the_right_shot():
    out = add_captions(SCAFFOLDED, {"s01": [cap("hello", at=1.5, dur=2.5)]})
    d = load(out)
    by_id = {s["id"]: s for s in d["shots"]}
    assert by_id["s01"]["captions"][0]["text"] == "hello"
    assert by_id["s01"]["captions"][0]["at"] == 1.5
    assert "captions" not in by_id["s00"]
    assert "captions" not in by_id["s02"]


def test_nothing_else_about_the_shot_changes():
    out = add_captions(SCAFFOLDED, {"s01": [cap("hello")]})
    d = load(out)
    s01 = {s["id"]: s for s in d["shots"]}["s01"]
    assert s01["speed"] == 1.2 and s01["amount"] == 0.6
    assert s01["in"] == "00:00.00" and s01["out"] == "00:07.41"
    assert s01["note"].startswith("kept whole")


def test_the_last_shot_can_be_captioned():
    """The end of the file is not the end of a shot's block, and the
    insertion point has to be found without a following `- id:` line."""
    out = add_captions(SCAFFOLDED, {"s02": [cap("the harbour")]})
    d = load(out)
    assert {s["id"]: s for s in d["shots"]}["s02"]["captions"][0]["text"] \
        == "the harbour"
    assert "# 3 shots, about 16 seconds." in out


def test_a_trailing_comment_stays_outside_the_shot():
    """The footer must not be swallowed into the last shot's block."""
    out = add_captions(SCAFFOLDED, {"s02": [cap("x")]})
    lines = out.splitlines()
    assert lines[-1].strip() == "# 3 shots, about 16 seconds." or \
        "# 3 shots, about 16 seconds." in lines[-2:]


def test_several_shots_at_once():
    out = add_captions(SCAFFOLDED,
                       {"s01": [cap("one"), cap("two", at=4.0)],
                        "s02": [cap("three")]})
    by_id = {s["id"]: s for s in load(out)["shots"]}
    assert [c["text"] for c in by_id["s01"]["captions"]] == ["one", "two"]
    assert [c["text"] for c in by_id["s02"]["captions"]] == ["three"]


def test_captions_are_appended_to_ones_already_there():
    """The promise the command makes: existing captions are kept."""
    first = add_captions(SCAFFOLDED, {"s01": [cap("first")]})
    second = add_captions(first, {"s01": [cap("second", at=4.0)]})
    caps = {s["id"]: s for s in load(second)["shots"]}["s01"]["captions"]
    assert [c["text"] for c in caps] == ["first", "second"]
    assert second.count("captions:") == 1     # one key, not two


def test_an_unknown_shot_id_is_skipped_not_guessed_at():
    out = add_captions(SCAFFOLDED, {"s99": [cap("nowhere")]})
    assert "nowhere" not in out
    assert load(out) == load(SCAFFOLDED)


def test_quotes_and_colons_in_a_line_cannot_break_the_file():
    """Whisper writes what it heard, and it heard punctuation."""
    nasty = 'She said: "well, it\'s 3:15" -- and #hashtags too'
    out = add_captions(SCAFFOLDED, {"s01": [cap(nasty)]})
    caps = {s["id"]: s for s in load(out)["shots"]}["s01"]["captions"]
    assert caps[0]["text"] == nasty


def test_accented_text_survives():
    out = add_captions(SCAFFOLDED, {"s01": [cap("Zima nad morzem, Kołobrzeg")]})
    caps = {s["id"]: s for s in load(out)["shots"]}["s01"]["captions"]
    assert caps[0]["text"] == "Zima nad morzem, Kołobrzeg"


@pytest.mark.parametrize("indent", ["  ", "    ", ""])
def test_whatever_indentation_the_file_uses(indent):
    """The bench writes two spaces, safe_dump writes none, and a person
    editing by hand writes whatever they like."""
    text = (f"fps: 24\nshots:\n{indent}- id: s01\n"
            f"{indent}  src: media/a.jpg\n{indent}  duration: 4.0\n")
    out = add_captions(text, {"s01": [cap("hi")]})
    d = load(out)
    assert d["shots"][0]["captions"][0]["text"] == "hi"
    assert d["shots"][0]["duration"] == 4.0


def test_a_film_with_keys_after_the_shots_block():
    """`shots:` is not always last, and the block must end where the
    next top-level key begins -- not swallow it."""
    text = ("fps: 24\n"
            "shots:\n"
            "  - id: s01\n"
            "    src: media/a.jpg\n"
            "    duration: 4.0\n"
            "\n"
            "music_volume: 0.6\n")
    out = add_captions(text, {"s01": [cap("hi")]})
    d = load(out)
    assert d["music_volume"] == 0.6
    assert d["shots"][0]["captions"][0]["text"] == "hi"


def test_the_footer_stops_saying_captions_are_missing_once_they_are_in():
    """`film init` signs off with "Speech captions are left out on
    purpose -- run film caption". After `film go` had put 48 captions in,
    the file still said so."""
    footer = ("# 3 shots, about 16 seconds.\n"
              "# Speech captions are left out on purpose -- run\n"
              "# `uv run film caption` once you're happy with the shots,\n"
              "# or watch it once and add what actually needs saying.\n")
    text = SCAFFOLDED.replace("# 3 shots, about 16 seconds.\n", footer)
    out = add_captions(text, {"s01": [cap("Hello there.")]})
    assert "left out on purpose" not in out
    assert "# 3 shots, about 16 seconds." in out
    assert load(out)["shots"][1]["captions"][0]["text"] == "Hello there."


def test_the_footer_stays_when_nothing_was_captioned():
    footer = "# Speech captions are left out on purpose -- run\n"
    text = SCAFFOLDED + footer
    assert "left out on purpose" in add_captions(text, {"s09": [cap("x")]})
