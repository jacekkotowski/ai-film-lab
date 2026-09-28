"""
A name the transcriber misheard does not take its line off the screen.

What Is Love, 2026-09-28. The narration said "In one study, researchers
examined 3,003 fights ..." and "A 2018 meta-analysis by Kathrin Karsay,
Johannes Knoll and Jörg Matthes pooled 54 papers, ...". Whisper heard
every word, but wrote "three thousand and three", "Catherine Carcey",
"Johns", "York Metas". The matcher found nothing written for those, and
the gap they left inside the sentence was more than FALSE_START_GAP
words wide -- which is what a fluffed line and a fresh start look like.
So everything before the gap was dropped as a false start: "In one
study," and "A 2018 meta-analysis by Kathrin Karsay," never reached the
screen, and `film check` said OK.

The difference is countable. A false start adds heard words that have no
written words to go with them. A mishearing has about as many heard
words as the written ones it failed to match. The words below are what
faster-whisper `small` returned on that take (times in seconds of the
narration), cut down to the two sentences.
"""

from ffilm.voice import align_to_script


class W:
    def __init__(self, start, end, word):
        self.start, self.end, self.word = start, end, word


def heard(rows):
    return [W(*r) for r in rows]


STUDY = heard([
    (161.88, 162.36, " In"), (162.36, 162.58, " one"),
    (162.58, 163.06, " study"), (163.06, 163.84, " researchers"),
    (163.84, 164.98, " examined"), (164.98, 165.62, " three"),
    (165.62, 166.06, " thousand"), (166.06, 166.36, " and"),
    (166.36, 166.72, " three"), (166.72, 167.38, " fights"),
    (167.38, 168.34, " and"), (168.34, 168.62, " what"),
    (168.62, 169.06, " happened"), (169.06, 169.74, " afterwards."),
])

META = heard([
    (233.61, 234.09, " A"), (234.09, 234.91, " 2018"),
    (234.91, 236.01, " meta"), (236.01, 236.83, "-analysis"),
    (236.83, 238.11, " by"), (238.11, 238.79, " Catherine"),
    (238.79, 239.93, " Carcey,"), (239.99, 240.55, " Johns"),
    (240.55, 241.61, " Knoll"), (241.61, 242.01, " and"),
    (242.01, 242.39, " York"), (242.39, 243.33, " Metas"),
    (243.33, 244.51, " pulled"), (244.51, 245.63, " 54"),
    (245.63, 246.59, " papers,"), (247.25, 247.73, " 50"),
    (247.73, 248.55, " independent"), (248.55, 249.20, " studies"),
    (249.20, 249.60, " and"), (249.60, 250.60, " 261"),
    (250.60, 251.40, " effect"), (251.40, 252.67, " sizes."),
])

STUDY_UNIT = ("In one study, researchers examined 3,003 fights "
              "and what happened afterwards.")
META_UNIT = ("A 2018 meta-analysis by Kathrin Karsay, Johannes Knoll and "
             "Jörg Matthes pooled 54 papers, 50 independent studies and "
             "261 effect sizes.")


def test_a_number_said_in_words_keeps_the_start_of_its_sentence():
    out = align_to_script(STUDY, [STUDY_UNIT])
    assert out[0].text == "In one study,"
    assert out[0].start == 161.88
    assert " ".join(ln.text for ln in out) == STUDY_UNIT


def test_a_misheard_name_keeps_its_line_in_the_script_spelling():
    out = align_to_script(META, [META_UNIT])
    texts = [ln.text for ln in out]
    assert texts[0] == "A 2018 meta-analysis by Kathrin Karsay,"
    assert " ".join(texts) == META_UNIT


def test_the_misheard_words_lend_their_times_to_the_written_ones():
    """"Kathrin Karsay" was said at 238.11-239.93, heard as "Catherine
    Carcey". The line ends where Karsay was said, and the next begins at
    "Johns" -- heard times, script words, nothing made up."""
    out = align_to_script(META, [META_UNIT])
    assert out[0].end == 239.93
    assert out[1].text.startswith("Johannes Knoll")
    assert out[1].start == 239.99
