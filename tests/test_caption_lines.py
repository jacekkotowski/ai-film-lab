"""
Where a caption is allowed to end.

Half a sentence on screen does not merely read badly. "I miss you and I
worry if you're okay do not be afraid" says something the speaker did
not say; the rest of it arrives a second and a half later, by which time
the viewer has already finished the wrong sentence for themselves.

The chunker used to break at punctuation and, failing that, at a count
of twelve words. That is fine until the transcript has no punctuation in
it -- which happens, and when it does, every single break is the count.

No speech model is involved here. `_chunk_words` takes anything with
.word, .start and .end, so these are made by hand.
"""

from ffilm.voice import MIN_WORDS, PAUSE, _chunk_words


class W:
    """One word, as faster-whisper hands it over -- leading space and all."""

    def __init__(self, word, start, end):
        self.word, self.start, self.end = word, start, end


def say(text: str, gap_after: dict | None = None, rate: float = 0.3):
    """Words spoken evenly, with a longer silence wherever you say so.

    `gap_after={3: 0.6}` puts a six-tenths of a second breath after the
    fourth word.
    """
    gap_after = gap_after or {}
    words, t = [], 0.0
    for i, w in enumerate(text.split()):
        words.append(W(" " + w, t, t + rate))
        t += rate + gap_after.get(i, 0.02)
    return words


def texts(lines):
    return [ln.text for ln in lines]


# --------------------------------------------------------------------------
# Punctuation, when there is any
# --------------------------------------------------------------------------

def test_a_full_stop_ends_a_line():
    out = _chunk_words(say("You are enough. You always were."))
    assert texts(out) == ["You are enough.", "You always were."]


def test_a_question_mark_ends_a_line():
    out = _chunk_words(say("You choose goodness, okay? I love you."))
    assert texts(out)[-1] == "I love you."


def test_a_comma_only_breaks_once_there_is_something_to_read():
    """Breaking at every comma leaves two-word captions flashing past."""
    out = _chunk_words(say("Well, I record this to say I believe in you."))
    assert out[0].text != "Well,"


# --------------------------------------------------------------------------
# The breath, when there is not
# --------------------------------------------------------------------------

def test_a_pause_ends_a_line_even_with_no_punctuation_at_all():
    """The case this was written for. Whisper punctuated this recording
    barely at all, so the only rule left was the word count, and the
    word count cut sentences in half."""
    out = _chunk_words(say("i miss you and i worry if you are ok",
                           gap_after={4: PAUSE + 0.2}))
    assert texts(out) == ["i miss you and i", "worry if you are ok"]


def test_a_gap_between_ordinary_words_is_not_a_pause():
    out = _chunk_words(say("do not be afraid of me"))
    assert len(out) == 1


def test_a_pause_too_early_does_not_strand_one_word():
    """A breath after the first word is a hesitation, not a sentence."""
    out = _chunk_words(say("i miss you and i worry about you",
                           gap_after={0: PAUSE + 0.5}))
    assert all(len(ln.text.split()) >= MIN_WORDS for ln in out)


def test_an_ellipsis_is_a_hesitation_not_a_full_stop():
    """Straight out of a real script: "You... feel and know what is
    good" is one sentence. Cut after "You..." it is a caption that says
    nothing, followed by one that sounds like an instruction."""
    out = _chunk_words(say("You... feel and know what is good"))
    assert texts(out) == ["You... feel and know what is good"]


def test_a_unicode_ellipsis_counts_too():
    out = _chunk_words(say("You… feel and know what is good"))
    assert len(out) == 1


# --------------------------------------------------------------------------
# When a line has to be cut for length anyway
# --------------------------------------------------------------------------

def test_a_forced_break_lands_on_the_widest_silence():
    """It has to break somewhere. Where they breathed most beats
    whatever word the counter happened to reach."""
    words = say("one two three four five six seven eight nine ten "
                "eleven twelve thirteen fourteen",
                gap_after={7: PAUSE - 0.12}, rate=0.2)
    out = _chunk_words(words, max_words=12)
    assert out[0].text == "one two three four five six seven eight"


def test_a_forced_break_never_leaves_a_fragment():
    words = say("one two three four five six seven eight nine ten "
                "eleven twelve thirteen fourteen",
                gap_after={0: PAUSE - 0.12}, rate=0.2)
    out = _chunk_words(words, max_words=12)
    assert all(len(ln.text.split()) >= MIN_WORDS for ln in out)


def test_words_with_no_silence_anywhere_still_get_broken_up():
    """A run-on with no gaps at all still cannot be one long caption."""
    out = _chunk_words(say("word " * 40, rate=0.2), max_words=12)
    assert len(out) > 1
    assert all(len(ln.text.split()) <= 12 for ln in out)


# --------------------------------------------------------------------------
# Nothing lost, nothing invented
# --------------------------------------------------------------------------

def test_every_word_survives_in_order():
    said = ("i record this to say i believe in you daily i hear your "
            "silence quite loud i miss you and worry if you are ok")
    out = _chunk_words(say(said, gap_after={8: 0.5, 15: 0.6}))
    assert " ".join(texts(out)).split() == said.split()


def test_the_times_stay_inside_the_words_they_came_from():
    words = say("you are enough you always were even this morning",
                gap_after={2: 0.5})
    out = _chunk_words(words)
    assert out[0].start == words[0].start
    assert out[-1].end == words[-1].end
    for a, b in zip(out, out[1:]):
        assert a.end <= b.start


def test_a_stray_last_word_is_folded_onto_the_line_before():
    """One word alone on screen reads as a glitch, not as a stress."""
    out = _chunk_words(say("do not be afraid of them. please",
                           gap_after={5: 0.6}))
    assert texts(out) == ["do not be afraid of them. please"]


def test_silence_produces_no_captions():
    assert _chunk_words([]) == []


# --------------------------------------------------------------------------
# Breaking the captions where YOU broke them
# --------------------------------------------------------------------------

from ffilm.voice import align_to_script, lines_for, script_units


def test_the_script_is_cut_where_its_author_cut_it():
    """A line break you typed is a decision -- booth.reflow already kept
    it. A full stop inside a line is the other place a caption may end."""
    assert script_units("One thing. Two things.\nA line I broke myself.") == \
        ["One thing.", "Two things.", "A line I broke myself."]


def test_blank_lines_and_stray_space_do_not_become_captions():
    assert script_units("\n\n  Only this.  \n\n") == ["Only this."]


def test_a_caption_takes_its_words_from_the_page_and_its_times_from_the_ear():
    """The whole point. Whisper heard no punctuation and ran two
    sentences together; the script knows where they part."""
    words = say("i miss you and i worry if you are ok do not be afraid")
    units = ["I miss you and I worry if you are ok.", "Do not be afraid."]
    out = align_to_script(words, units)
    assert texts(out) == units
    assert out[0].start == words[0].start
    assert out[1].end == words[-1].end
    assert out[0].end <= out[1].start


def test_punctuation_and_case_do_not_stop_a_match():
    words = say("nagrywam to zeby powiedziec ze w ciebie wierze")
    out = align_to_script(words, ["Nagrywam to, zeby powiedziec, "
                                  "ze w ciebie wierze!"])
    assert len(out) == 1


def test_a_line_you_fluffed_and_read_again_keeps_the_second_reading():
    """You stumble, stop, and say the sentence properly. Both readings
    are in the transcript; only one of them is the take."""
    words = say("do not be do not be afraid of them")
    out = align_to_script(words, ["Do not be afraid of them."])
    assert len(out) == 1
    # timed from the good reading, not from the false start
    assert out[0].start > words[0].start


def test_a_sentence_you_wrote_but_never_said_is_not_captioned():
    words = say("only the first one")
    out = align_to_script(words, ["Only the first one.", "This never got said."])
    assert texts(out) == ["Only the first one."]


def test_no_script_means_listen_instead():
    words = say("You are enough. You always were.")
    assert lines_for(words, None) == _chunk_words(words)
    assert lines_for(words, "   ") == _chunk_words(words)


def test_improvising_falls_back_to_listening():
    """The script said one thing and you said something else entirely.
    Forcing the page onto that would caption words nobody spoke."""
    words = say("actually let me say something completely different today")
    out = lines_for(words, "A prepared sentence that bears no relation.")
    assert texts(out) == texts(_chunk_words(words))


def test_captions_never_run_backwards():
    words = say("second thing first thing")
    out = align_to_script(words, ["First thing.", "Second thing."])
    for a, b in zip(out, out[1:]):
        assert a.start <= b.start


def test_a_sentence_spanning_two_breaths_is_captioned_once():
    """Whisper splits on breaths, not on sentences. Aligning each of its
    segments separately found the same written sentence in both and put
    it on screen twice -- 4 of 23 sentences, on a real take."""
    units = ["I lose my backpack, everything I own is in it."]
    first_breath = say("i lose my backpack")
    second = say("everything i own is in it", rate=0.3)
    for w in second:                       # lay it after the first breath
        w.start += 5.0
        w.end += 5.0
    out = align_to_script(first_breath + second, units)
    # It may well be cut in two -- five seconds apart, it SHOULD be --
    # but each half appears once, and between them they say the sentence.
    joined = " ".join(texts(out))
    assert joined.count("backpack") == 1
    assert joined.count("everything") == 1


# --------------------------------------------------------------------------
# Short enough to read
# --------------------------------------------------------------------------

from ffilm.voice import CAPTION_CHARS, CAPTION_SECONDS


def test_a_long_sentence_is_cut_at_its_own_commas():
    """Putting a whole written sentence on screen unbroken made the print
    small (render.fit_caption shrinks until it fits) and left silent gaps
    (caption_fit clamps the display to 4.5s). Measured on a real take:
    one sentence ran 9.4 seconds, so it showed for 4.5 and left 4.9
    seconds of talking with nothing on screen."""
    unit = ("I got there early, pranked my way in a year ahead, "
            "passed the exam before anyone expected me to.")
    words = say(unit.replace(",", ""), rate=0.5)
    out = align_to_script(words, [unit])
    assert len(out) > 1, "a nine second sentence must not be one caption"
    for ln in out:
        assert ln.dur <= CAPTION_SECONDS + 0.6
        assert len(ln.text) <= CAPTION_CHARS + 12


def test_the_pieces_still_say_the_whole_sentence():
    unit = "I got there early, and it did not matter at all in the end."
    words = say(unit.replace(",", ""), rate=0.5)
    said = " ".join(texts(align_to_script(words, [unit])))
    for w in ("early", "matter", "end"):
        assert w in said


def test_a_short_sentence_is_left_in_one_piece():
    """Cutting is for sentences that need it. This one does not."""
    out = align_to_script(say("and it didn't matter"), ["And it didn't matter."])
    assert texts(out) == ["And it didn't matter."]


def test_thirteen_short_words_are_still_one_caption():
    """Counting words got this wrong in both directions. This sentence is
    thirteen words, fifty-six characters and three and a half seconds --
    one comfortable caption -- and a word ceiling cut it in two."""
    unit = "I wanted to prove to the girl I loved that I was worthy."
    out = align_to_script(say(unit.strip("."), rate=0.26), [unit])
    assert texts(out) == [unit]


def test_a_caption_is_measured_in_ink_not_in_words():
    long_words = ("Extraordinarily complicated pronunciations overwhelm tired readers.")
    assert len(long_words) > CAPTION_CHARS
    out = align_to_script(say(long_words.strip("."), rate=0.5), [long_words])
    assert len(out) > 1


def test_with_no_real_breath_the_line_is_filled_not_halved():
    """Measured on a real take: the winning gap was 0.00s, and it cut
    "He was pulling fresh | readings from weather balloons" for no
    reason. Given nothing to go on, fill the caption."""
    unit = ("He was pulling fresh readings from weather balloons "
            "and ships and stations.")
    out = align_to_script(say(unit.strip("."), rate=0.22), [unit])
    assert len(out) > 1
    assert len(out[0].text.split()) >= 6, \
        f"first caption is a stub: {out[0].text!r}"


def test_a_hyphen_or_an_apostrophe_does_not_stop_the_splitting():
    """`_key` makes two tokens of "decision-maker" and two of "can't",
    so the count of words on the page and the count matched against the
    transcript drift apart. Comparing them directly made the splitter
    give up without a word -- and a seventy-three character, seven
    second caption reached the screen with both ceilings in force."""
    unit = ("and a decision-maker who has to pick one under a deadline "
            "he can't move.")
    out = align_to_script(say(unit.strip("."), rate=0.4), [unit])
    assert len(out) > 1, "it must still be cut"
    for ln in out:
        assert len(ln.text) <= CAPTION_CHARS + 12
        assert ln.dur <= CAPTION_SECONDS + 1.0


def test_a_word_longer_than_the_ceiling_does_not_crash():
    """It cannot be cut in half, however long it is. Without a guard the
    splitter recursed until it indexed past the end of its own offsets
    and raised IndexError."""
    word = ("Donaudampfschiffahrtselektrizitaetenhauptbetriebswerk"
            "bauunterbeamtengesellschaft")
    assert len(word) > CAPTION_CHARS
    out = align_to_script(say(word), [word + "."])
    assert len(out) == 1


def test_the_clock_never_breaks_a_phrase():
    """From one real film, twice. When the clock could cut anywhere:

        the recognition of / that murder as / the "law of laws."

    When it could cut only at a real pause -- still wrong, because the
    speaker paused half a second after "that", for emphasis, in the
    middle of the phrase:

        the recognition of that / murder as the "law of laws."

    A pause in speech is not a boundary in a sentence, and without a
    parser nothing can tell which is which. Fifty-two characters is one
    caption however long it took to say."""
    unit = 'the recognition of that murder as the "law of laws."'
    assert len(unit) <= CAPTION_CHARS
    for words in (say(unit.strip("."), rate=0.6),                # slow
                  say(unit.strip("."), gap_after={3: 0.6})):     # slow + pause
        out = align_to_script(words, [unit])
        assert len(out) == 1, f"chopped into {[l.text for l in out]}"


def test_a_sentence_that_ends_in_a_quote_mark_still_ends():
    """The character before the space is the quote, not the stop:

        the "law of laws." From care to hatred.

    stayed one unit, blew the character ceiling, and was cut mid-phrase
    into `the recognition of that` / `murder as the "law of laws." ...`.
    Straightth from a real film."""
    units = script_units('the recognition of that murder as the '
                         '"law of laws." From care to hatred.')
    assert units == ['the recognition of that murder as the "law of laws."',
                     "From care to hatred."]


def test_closing_brackets_and_curly_quotes_count_too():
    assert len(script_units("He said it (loudly.) Then he left.")) == 2
    assert len(script_units("She wrote \u201cno.\u201d He agreed.")) == 2


# --------------------------------------------------------------------------
# A sentence read twice, with a pause between
# --------------------------------------------------------------------------

def later(words, by):
    for w in words:
        w.start += by
        w.end += by
    return words


def test_a_sentence_read_twice_is_captioned_twice():
    """You read a sentence, paused, and read it again. The edit cuts at
    the pause and keeps BOTH readings as shots -- so both need their
    words on screen. Keeping only the last reading left 8 talking shots,
    47.5s of a 216s film, with no caption at all ("I am not your fear",
    2026-09-16)."""
    unit = "I am not the fear you are holding onto."
    first = say("i am not the fear you are holding onto")
    second = later(say("i am not the fear you are holding onto"), 12.0)
    out = align_to_script(first + second, [unit])
    assert texts(out) == [unit, unit]
    assert out[0].start == first[0].start
    assert out[1].start == second[0].start


def test_a_second_reading_of_several_sentences_gets_all_of_them():
    units = ["You are strong.", "You are essential to this world."]
    first = say("you are strong you are essential to this world")
    second = later(say("you are strong you are essential to this world"), 15.0)
    out = align_to_script(first + second, units)
    assert texts(out) == units + units


def test_two_stumbled_words_before_a_pause_are_still_not_captioned():
    """A false start is not a reading. Two words of it, even with a
    breath after, must not put the whole sentence on screen."""
    unit = "Do not be afraid of them."
    stumble = say("do not")
    good = later(say("do not be afraid of them"), 3.0)
    out = align_to_script(stumble + good, [unit])
    assert len(out) == 1
    assert out[0].start == good[0].start


def test_something_you_improvised_between_readings_is_not_captioned():
    unit = "I love you."
    words = (say("i love you")
             + later(say("wait let me start that over now"), 3.0)
             + later(say("i love you"), 8.0))
    out = align_to_script(words, [unit])
    assert all(t == unit for t in texts(out))


def test_a_reading_is_captioned_even_when_the_next_one_starts_with_a_stumble():
    """On the real take, every missed reading ran straight into the first
    word of the next attempt: "...disrespected you. I'm" -- then "I am not
    the fear..." again. The pause that matters is the one around the
    CAPTION, not around the leftover speech."""
    units = ["Creating a wall.", "I am not the fear you are holding onto.",
             "Though I am learning."]
    words, t = [], 0.0

    def add(text, gap):
        nonlocal t
        ws = later(say(text), t + gap)
        words.extend(ws)
        t = ws[-1].end

    add("creating a wall", 0.0)
    add("i am not the fear you are holding onto", 1.8)
    add("i'm", 1.5)                              # the stumble
    add("i am not the fear you are holding onto", 0.3)
    add("though i am learning", 1.0)
    out = align_to_script(words, units)
    assert texts(out) == [units[0], units[1], units[1], units[2]]
