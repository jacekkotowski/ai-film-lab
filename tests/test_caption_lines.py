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
