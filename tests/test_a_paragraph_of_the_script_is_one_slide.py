"""
One paragraph of script.txt is one slide.

`film init` cuts a narration at its longest pauses, which is a guess and
says so. On `projects/test_story` the two longest pauses fall at 34.45
and 50.55, so the guess gave slides of 33.4 / 14.2 / 6.8 seconds -- the
first picture holding for most of the film. Where somebody paused is
not where they changed subject.

The script is where they said so. A blank line between two paragraphs
is a decision, exactly the way a line break inside one already is (see
voice.script_units and booth.reflow). So: one paragraph, one picture,
and the slide runs from the first word of that paragraph to the last.

A paragraph may name its picture on its first line, `[3]` or
`[3_declaration_of_love.png]`. Otherwise they are handed out in order.

The times come from `voice.align_to_script`, which already gives every
written sentence the times of the words that said it. All this adds is
which paragraph each sentence was in.

Fake words throughout, as in test_caption_lines.py. No speech model.
"""

from dataclasses import dataclass

from pytest import approx

from ffilm import scaffold, voice
from ffilm.scaffold import BREATH
from ffilm.spec import Film, Shot
from ffilm.voice import Line, paragraph_windows, script_paragraphs


@dataclass
class W:
    """One word as the speech model hands it back."""
    word: str
    start: float
    end: float


def said(text: str, at: float = 0.0, gap: float = 0.5) -> list[W]:
    out, t = [], at
    for w in text.split():
        out.append(W(w, round(t, 2), round(t + 0.4, 2)))
        t += gap
    return out


SCRIPT = """I remember I was stressed. I just said what I just said.

I had a hidden rose behind me. She answered me.

It would be easier if you forget me. But I did not."""


# --------------------------------------------------------------------------
# Reading the script
# --------------------------------------------------------------------------

def test_a_blank_line_starts_a_new_paragraph():
    paras = script_paragraphs(SCRIPT)
    assert len(paras) == 3
    assert paras[0].units == ["I remember I was stressed.",
                              "I just said what I just said."]
    assert paras[2].units == ["It would be easier if you forget me.",
                              "But I did not."]


def test_a_line_break_inside_a_paragraph_is_not_a_new_one():
    """`script_units` already treats every line break as a place a
    caption may end. Only a BLANK line changes the picture."""
    paras = script_paragraphs("one line\nanother line\n\nsecond para")
    assert len(paras) == 2
    assert paras[0].units == ["one line", "another line"]


def test_a_paragraph_can_name_its_picture():
    paras = script_paragraphs("[3] the last one first.\n\nthen this.")
    assert paras[0].picture == "3"
    assert paras[0].units == ["the last one first."]
    assert paras[1].picture is None


def test_a_paragraph_can_name_its_picture_by_filename():
    paras = script_paragraphs("[3_declaration_of_love.png] words here.")
    assert paras[0].picture == "3_declaration_of_love.png"


def test_the_picture_tag_never_reaches_the_screen():
    """It is an instruction to the machine, not something to caption."""
    assert "[" not in " ".join(voice.script_units("[3] hello there."))


def test_the_units_of_the_paragraphs_are_the_units_of_the_script():
    """Built the same way by construction, so a sentence cannot belong
    to one paragraph for the matcher and another for the cutting."""
    flat = [u for p in script_paragraphs(SCRIPT) for u in p.units]
    assert flat == voice.script_units(SCRIPT)


# --------------------------------------------------------------------------
# Where each paragraph was said
# --------------------------------------------------------------------------

def aligned(script: str, spoken: str, at: float = 1.0) -> list[Line]:
    return voice.align_to_script(said(spoken, at), voice.script_units(script))


def test_each_sentence_remembers_which_unit_it_came_from():
    lines = aligned("First one. Second one.", "first one second one")
    assert [ln.unit for ln in lines] == [0, 1]


def test_a_paragraph_runs_from_its_first_word_to_its_last():
    paras = script_paragraphs(SCRIPT)
    lines = aligned(SCRIPT,
                    "I remember I was stressed I just said what I just said "
                    "I had a hidden rose behind me she answered me "
                    "It would be easier if you forget me but I did not")
    windows = paragraph_windows(lines, paras)
    assert len(windows) == 3
    for w in windows:
        assert w is not None
    for a, b in zip(windows, windows[1:]):
        assert a[1] <= b[0]                       # in order, never overlapping


def test_a_breath_is_left_either_side_of_a_paragraph():
    """The same breath `scaffold` leaves when it cuts a take at a pause,
    so the first and last words are not clipped."""
    paras = script_paragraphs("Only this.\n\nAnd this.")
    lines = aligned("Only this.\n\nAnd this.", "only this and this", at=10.0)
    first = paragraph_windows(lines, paras)[0]
    said_at = min(ln.start for ln in lines if ln.unit == 0)
    assert first[0] == approx(max(0.0, said_at - BREATH))


def test_a_paragraph_nobody_read_out_has_no_window():
    paras = script_paragraphs("Said out loud.\n\nSkipped entirely.")
    lines = aligned("Said out loud.\n\nSkipped entirely.", "said out loud")
    assert paragraph_windows(lines, paras)[1] is None


def test_two_paragraphs_never_claim_the_same_second():
    """Padding by a breath at both ends can make neighbours overlap, and
    two slides quoting the same moment would say it twice."""
    paras = script_paragraphs("One.\n\nTwo.")
    lines = [Line("One.", 1.0, 2.0), Line("Two.", 2.1, 3.0)]
    lines[0].unit, lines[1].unit = 0, 1
    a, b = paragraph_windows(lines, paras)
    assert a[1] <= b[0]


# --------------------------------------------------------------------------
# Which picture goes with which paragraph
# --------------------------------------------------------------------------

def slides(*names) -> Film:
    return Film(shots=[
        Shot(src=f"media/{n}", kind="still", voice="media/vo.wav",
             tin=0.0, tout=1.0, duration=1.4, id=f"s{i:02d}")
        for i, n in enumerate(names, 1)])


def windows(n):
    return [(float(i * 10), float(i * 10 + 8)) for i in range(n)]


def test_one_paragraph_each_in_order():
    film = slides("a.png", "b.png", "c.png")
    cuts = scaffold.slide_cuts(film, script_paragraphs(SCRIPT), windows(3))
    assert [c.src for c in cuts] == ["media/a.png", "media/b.png",
                                     "media/c.png"]
    assert [c.sid for c in cuts] == ["s01", "s02", "s03"]


def test_a_paragraph_that_names_a_picture_gets_that_picture():
    film = slides("1a.png", "2b.png", "3c.png")
    paras = script_paragraphs("[3] third.\n\nsecond.\n\nfirst.")
    cuts = scaffold.slide_cuts(film, paras, windows(3))
    assert cuts[0].src == "media/3c.png"


def test_a_picture_can_be_named_by_its_filename():
    film = slides("1a.png", "2b.png", "3c.png")
    paras = script_paragraphs("[2b.png] words.\n\nmore.")
    cuts = scaffold.slide_cuts(film, paras, windows(2))
    assert cuts[0].src == "media/2b.png"


def test_more_paragraphs_than_pictures_reuses_the_last_picture():
    film = slides("a.png", "b.png")
    cuts = scaffold.slide_cuts(film, script_paragraphs(SCRIPT), windows(3))
    assert [c.src for c in cuts] == ["media/a.png", "media/b.png",
                                     "media/b.png"]
    assert cuts[2].sid == ""              # a shot that has to be added


def test_more_pictures_than_paragraphs_share_the_last_paragraph():
    """Divided between them, not repeated: two slides quoting the same
    words would say them twice."""
    film = slides("a.png", "b.png", "c.png")
    paras = script_paragraphs("first para.\n\nsecond para.")
    cuts = scaffold.slide_cuts(film, paras, [(0.0, 10.0), (20.0, 40.0)])
    assert len(cuts) == 3
    assert (cuts[1].tin, cuts[1].tout) == (approx(20.0), approx(30.0))
    assert (cuts[2].tin, cuts[2].tout) == (approx(30.0), approx(40.0))


def test_a_paragraph_that_was_never_said_takes_no_picture():
    film = slides("a.png", "b.png")
    paras = script_paragraphs("said.\n\nskipped.\n\nsaid too.")
    cuts = scaffold.slide_cuts(film, paras, [(0.0, 5.0), None, (9.0, 14.0)])
    assert len(cuts) == 2
    assert [c.src for c in cuts] == ["media/a.png", "media/b.png"]


# --------------------------------------------------------------------------
# Writing it back into film.yaml, as text
# --------------------------------------------------------------------------

YAML = '''fps: 24
resolution: [1080, 1920]

shots:

  - id: s00
    src: analysis/title.jpg
    duration: 2.0
    move: static

  - id: s01
    src: media/a.png
    voice: media/vo.wav
    in: "00:01.75"
    out: "00:34.75"
    move: tilt_up
    focus: [0.649, 0.539]
    note: "picture 1 of 3 -- holds while these words are said"

  - id: s02
    src: media/b.png
    voice: media/vo.wav
    in: "00:37.10"
    out: "00:50.85"
    move: push_in
    focus: [0.668, 0.565]

# 3 shots, about 54 seconds.
'''


def cut(sid, src, tin, tout, note="") -> scaffold.SlideCut:
    return scaffold.SlideCut(sid=sid, src=src, voice="media/vo.wav",
                             tin=tin, tout=tout, note=note)


def test_a_recut_slide_keeps_everything_that_was_not_its_words():
    out = scaffold.recut_slides(YAML, [cut("s01", "media/a.png", 2.0, 20.0),
                                       cut("s02", "media/b.png", 21.0, 40.0)])
    assert 'in: "00:02.00"' in out
    assert 'out: "00:20.00"' in out
    assert 'in: "00:01.75"' not in out
    # Untouched: the move, the focus point, the title card, the comments.
    assert "move: tilt_up" in out
    assert "focus: [0.649, 0.539]" in out
    assert "src: analysis/title.jpg" in out
    assert "# 3 shots, about 54 seconds." in out


def test_a_recut_slide_can_change_its_picture():
    out = scaffold.recut_slides(YAML, [cut("s01", "media/c.png", 2.0, 20.0)])
    assert "src: media/c.png" in out
    assert "src: media/a.png" not in out


def test_an_extra_slide_is_added_at_the_end_of_the_shots():
    out = scaffold.recut_slides(YAML, [
        cut("s01", "media/a.png", 2.0, 20.0),
        cut("s02", "media/b.png", 21.0, 40.0),
        cut("", "media/b.png", 41.0, 50.0, note="paragraph 3 of 3")])
    ids = [ln.strip() for ln in out.splitlines() if "- id:" in ln]
    assert ids == ["- id: s00", "- id: s01", "- id: s02", "- id: s03"]
    # Before the footer, not after it -- outside `shots:` nothing reads it.
    assert out.index("- id: s03") < out.index("# 3 shots")


def test_the_file_stops_saying_the_cuts_were_guessed():
    """`init` writes that it guessed the cuts from the pauses. Once a
    script has said where the paragraphs are, that is no longer true --
    the same reason `add_captions` takes out NO_CAPTIONS_YET."""
    guessed = YAML + "\n".join(("",) + scaffold.SLIDES_GUESSED) + "\n"
    out = scaffold.recut_slides(guessed,
                                [cut("s01", "media/a.png", 2.0, 20.0)])
    assert "GUESSED" not in out
    assert scaffold.SLIDES_BY_SCRIPT[0] in out


def test_the_note_says_which_paragraph_this_picture_holds():
    out = scaffold.recut_slides(YAML, [
        cut("s01", "media/a.png", 2.0, 20.0, note="paragraph 1 of 3")])
    assert "paragraph 1 of 3" in out
    assert "picture 1 of 3" not in out


def test_the_preview_is_fitted_against_the_new_windows():
    """`caption` without --apply writes nothing, and its preview has to
    show the film the script asks for -- not the one being replaced."""
    film = slides("a.png", "b.png")
    after = scaffold.apply_cuts(film, [cut("s01", "media/a.png", 2.0, 20.0),
                                       cut("s02", "media/b.png", 21.0, 40.0)])
    assert [s.tin for s in after.shots] == [approx(2.0), approx(21.0)]
    assert after.shots[0].duration == approx(18.0 + 0.4)
    assert [s.tin for s in film.shots] == [0.0, 0.0]      # untouched


def test_an_extra_slide_joins_the_film_in_memory_too():
    film = slides("a.png", "b.png")
    after = scaffold.apply_cuts(film, [
        cut("s01", "media/a.png", 2.0, 20.0),
        cut("s02", "media/b.png", 21.0, 40.0),
        cut("", "media/b.png", 41.0, 50.0)])
    assert [s.id for s in after.shots] == ["s01", "s02", "s03"]
    assert after.shots[2].src == "media/b.png"


def test_what_it_writes_is_a_film_that_loads(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    for n in ("a.png", "b.png", "vo.wav"):
        (media / n).write_bytes(b"")
    (tmp_path / "analysis").mkdir()
    (tmp_path / "analysis" / "title.jpg").write_bytes(b"")
    out = scaffold.recut_slides(YAML, [
        cut("s01", "media/a.png", 2.0, 20.0, note="paragraph 1 of 3"),
        cut("s02", "media/b.png", 21.0, 40.0, note="paragraph 2 of 3"),
        cut("", "media/b.png", 41.0, 50.0, note="paragraph 3 of 3")])
    (tmp_path / "film.yaml").write_text(out, encoding="utf-8")
    film = Film.load(tmp_path / "film.yaml")
    assert [s.id for s in film.shots] == ["s00", "s01", "s02", "s03"]
    assert film.shots[1].tin == approx(2.0)
    assert film.shots[3].src == "media/b.png"
    assert film.shots[3].tout == approx(50.0)
