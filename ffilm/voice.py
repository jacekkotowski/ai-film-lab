"""
voice.py  --  turn a spoken track into captions with real timestamps.

    uv run film caption -p my_movie

Runs entirely on your machine. Nothing is uploaded, no account, no
internet needed after the model downloads once. Uses faster-whisper
(CTranslate2), which is several times quicker than the reference
Whisper on a CPU-only laptop and needs no GPU.

What this solves: writing `at:`/`dur:` for captions by hand means
guessing when you said a line and re-rendering to check. This listens
to what you actually said and writes the timing for you. You keep only
the judgment call a machine cannot make -- which lines are worth
putting on screen, and which shot each one belongs to.

The model downloads once (about 460 MB for the default 'small' size) and
is cached by faster-whisper itself -- nothing this toolkit manages.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import kinds

AUDIO_EXT = kinds.AUDIO
VIDEO_EXT = kinds.VIDEO


@dataclass
class Line:
    text: str
    start: float
    end: float

    def __post_init__(self):
        # The speech model hands back numpy scalars, not Python floats.
        # They compare and arithmetic like floats, so nothing complains --
        # until one reaches yaml.dump, which writes it as
        # !!python/object/apply:numpy._core.multiarray.scalar and produces
        # a film.yaml that safe_load then refuses to read. Coerce at the
        # door, once, rather than hunting them downstream.
        self.text = str(self.text)
        self.start = float(self.start)
        self.end = float(self.end)

    @property
    def dur(self) -> float:
        return self.end - self.start


def has_audio_track(path: Path) -> bool:
    """Some clips are silent (a screen recording, a muted export). Check
    before trying to extract, so the error is clear instead of cryptic."""
    from .render import ffmpeg_bin, ffprobe_bin
    exe = ffprobe_bin()
    r = subprocess.run(
        [exe, "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return bool(r.stdout.strip())


def extract_audio(video: Path, out: Path) -> Path:
    """Pull the audio track out of a video file, once, to a plain wav.
    Re-used on later runs unless the source video is newer."""
    from .render import ffmpeg_bin, ffprobe_bin
    if out.exists() and out.stat().st_mtime > video.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(out)],
        capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise SystemExit(f"Could not extract audio from {video.name}: "
                         f"{r.stderr.strip()[-300:]}")
    return out


@dataclass
class VoiceSource:
    """One thing to transcribe, and -- for video -- which shot(s) in
    film.yaml it corresponds to, so lines land on the right shot even
    when several clips each have their own talking."""
    audio_path: Path        # extracted wav or original audio file
    label: str               # for messages: the file this came from
    shot_srcs: list[str]     # film.yaml `src:` values this audio covers
    time_offset: float = 0.0  # seconds to add: this clip's start, in the
                              # ORIGINAL file, if only part of it is used


def voice_sources(project: Path) -> list[VoiceSource]:
    """What can be transcribed, in priority order:

    1. A file named `voiceover.*` in media/ -- always wins outright, on
       the assumption that if you bothered to record and name one, that
       IS the narration, even if your clips also have sound.
    2. Any other standalone audio file in media/ (a phone voice memo,
       an mp3) -- same idea, just not specially named.
    3. Otherwise, every video clip that has its own audio track gets its
       audio extracted and transcribed separately -- this is "captions
       for me talking in the clips" with no extra recording needed.
    """
    media = project / "media"
    cache = project / "analysis" / "audio"

    named = sorted(media.glob("voiceover.*"))
    if named:
        return [VoiceSource(named[0], named[0].name, [])]

    standalone = [p for p in sorted(media.rglob("*"))
                 if p.suffix.lower() in AUDIO_EXT]
    if standalone:
        return [VoiceSource(standalone[0], standalone[0].name, [])]

    sources = []
    for p in sorted(media.rglob("*")):
        if p.suffix.lower() not in VIDEO_EXT:
            continue
        if not has_audio_track(p):
            continue
        rel = p.relative_to(project).as_posix()
        wav = cache / f"{p.stem}.wav"
        sources.append(VoiceSource(extract_audio(p, wav), p.name, [rel]))
    return sources


def find_voice_track(project: Path) -> Path | None:
    """Back-compat convenience: the single most relevant audio source,
    if you just want one file rather than the full priority list."""
    srcs = voice_sources(project)
    return srcs[0].audio_path if srcs else None


# The silence between two words that means the speaker finished a
# thought. Ordinary gaps between words in running speech are under a
# tenth of a second; a breath is a third of one or more.
PAUSE = 0.35

# Below this, a caption on its own reads as a glitch rather than as a
# line. Used both to refuse a break that would leave a fragment, and to
# fold a stray tail onto the line before it.
MIN_WORDS = 3


def _line(chunk: list) -> Line | None:
    text = "".join(x.word for x in chunk).strip()
    return Line(text, chunk[0].start, chunk[-1].end) if text else None


def _breath(chunk: list) -> int:
    """Where to cut a run of words that has to be cut somewhere.

    The widest silence in it -- because that is where the speaker
    paused, and a pause is where a sentence ends whether or not the
    transcript says so. Never so near either end that one side comes out
    a fragment. 0 means there is nowhere good.
    """
    best, where = 0.0, 0
    for i in range(MIN_WORDS, len(chunk) - MIN_WORDS + 1):
        gap = chunk[i].start - chunk[i - 1].end
        if gap > best:
            best, where = gap, i
    return where


def _chunk_words(words: list, max_words: int = 16) -> list[Line]:
    """Group words into on-screen lines, broken where the sense breaks.

    Whisper's own segments are often a whole breath or more -- too long
    to read comfortably as one caption. Three things end a line, in
    order of how much they mean:

    Real punctuation (. ! ?), which is the model telling us a sentence
    finished. Then a PAUSE, which is the SPEAKER telling us the same
    thing -- and which matters more than it sounds, because whisper
    punctuates some recordings barely at all, and on those the only
    other rule left was word count. Then a comma, once there is enough
    on screen to be worth breaking.

    The comma and word-count thresholds are deliberately generous --
    raised from the values this shipped with, which cut sentences at
    their first internal clause even when nothing about the audio
    called for it. A caption that runs a little long is still readable;
    one snapped off at a comma is a different sentence than the one
    spoken.

    Only when none of those has happened for `max_words` is a line cut
    for length, and even then it is cut at the widest silence inside it
    rather than at whatever word the counter happened to reach. Half a
    sentence on screen does not just read badly; it can read as
    something the speaker did not say.
    """
    lines: list[Line] = []
    chunk: list = []

    def flush() -> None:
        nonlocal chunk
        made = _line(chunk)
        if made:
            lines.append(made)
        chunk = []

    for w in words:
        # A breath before this word ends the line that came before it.
        if (len(chunk) >= MIN_WORDS
                and w.start - chunk[-1].end >= PAUSE):
            flush()
        chunk.append(w)

        word_text = w.word.strip()
        # An ellipsis is a hesitation, not a full stop. "You... feel and
        # know what is good" is one sentence, and breaking it after
        # "You..." leaves a caption that is a whole word of nothing.
        trailing_off = word_text.endswith(("...", "…"))
        if word_text.endswith((".", "!", "?")) and not trailing_off:
            flush()
        elif word_text.endswith(",") and len(chunk) >= 9:
            flush()
        elif len(chunk) >= max_words:
            cut = _breath(chunk)
            if cut:
                made = _line(chunk[:cut])
                if made:
                    lines.append(made)
                chunk = chunk[cut:]
            else:
                flush()

    if chunk:
        # Don't leave a stray one- or two-word caption dangling -- it
        # reads as a glitch, not a stress. Fold it onto the line before
        # it instead, if there is one.
        made = _line(chunk)
        if made and len(chunk) < MIN_WORDS and lines:
            prev = lines[-1]
            lines[-1] = Line(f"{prev.text} {made.text}", prev.start, made.end)
        elif made:
            lines.append(made)
    return lines


# --------------------------------------------------------------------------
# Breaking the captions where YOU broke them
#
# `_chunk_words` below decides where a caption ends by listening: real
# punctuation, then a breath, then a word count. It is a good guess, and
# it is still what happens when you improvised. But when there is a
# script.txt -- and there is, whenever you used the recording window --
# the guessing is unnecessary. You already decided where the sentences
# end, by typing them. This puts the words back into the shape you wrote,
# and uses the transcript only for the one thing it is actually
# authoritative about: WHEN each word was said.
#
# Nothing new is installed for this. difflib is in the standard library
# and a four hundred word script is nothing to it.
# --------------------------------------------------------------------------

# A gap this big between two runs of the same sentence means the first
# one was a false start -- you fluffed the line and read it again.
FALSE_START_GAP = 3


def _key(text: str) -> list[str]:
    """Words reduced to something two spellings of them can share.

    Casefolded and stripped of punctuation, because the transcript
    writes "Nagrywam," and the script writes "Nagrywam" -- and because
    whisper's commas are its own opinion, not yours.
    """
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def script_units(text: str) -> list[str]:
    """The script, cut where its author cut it.

    A line break you typed is a decision -- `booth.reflow` keeps those
    and flattens the ones a window put in, so by the time a script
    reaches here every remaining break is yours. Inside a line, a full
    stop is the other place a caption may end.
    """
    units: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?…])\s+", line):
            part = part.strip()
            if part:
                units.append(part)
    return units


# A caption has to be short enough to READ, and matching a script does
# not change that. Two separate ceilings, and both were breached the
# moment whole sentences went on screen unbroken:
#
#   seconds -- caption_fit clamps any caption to MAX_CAPTION_SECONDS
#   (4.5). A sentence taking 9.4s to say therefore showed for 4.5s and
#   left 4.9s of talking with nothing on screen at all.
#
#   words -- render.fit_caption WRAPS first and then SHRINKS the font
#   until the text fits in CAPTION_MAX_LINES. A long sentence is
#   therefore a small one, which is the other half of the same
#   complaint.
#
# Kept under caption_fit's own figure rather than equal to it, so the
# clamp there never has anything left to do.
CAPTION_SECONDS = 4.0

# Measured in CHARACTERS, not words, because that is what decides
# whether the type has to shrink. render.wrap_to_width wraps to the
# frame and render.fit_caption then shrinks the font until the result
# fits in CAPTION_MAX_LINES (3) -- so what matters is how much INK a
# caption is, and short words are not much.
#
# Counting words got this wrong in both directions: "I wanted to prove
# to the girl I loved that I was worthy" is thirteen words, fifty-six
# characters and three and a half seconds -- comfortably one caption --
# and a word ceiling cut it into "I wanted to prove" and a remainder.
CAPTION_CHARS = 62

# A backstop, not the rule. Nothing sensible reaches it.
CAPTION_WORDS = 18

# A breath cut may not leave less than this on either side. MIN_WORDS
# (3) was enough to permit "I wanted to", which is three words and no
# meaning.
BREATH_MIN_WORDS = 4

# A silence has to be at least this long to count as a place somebody
# chose to stop. Under it, one gap is no more meaningful than another.
REAL_BREATH = 0.12

# Where a sentence may be cut when it will not fit whole: at the marks
# its author already put in it.
CLAUSE_END = re.compile(r"(?<=[,;:—–-])\s+")


def _atoms(unit: str) -> list[str]:
    """One sentence, cut at its own internal punctuation. No punctuation
    means one atom, and it gets cut on time and word count instead."""
    return [a for a in CLAUSE_END.split(unit) if a.strip()]


def _pack(atoms: list[str], span, tokens_before: int) -> list[tuple[str, int, int]]:
    """Group clauses into caption-sized pieces.

    Returns (text, first token, last token+1) for each piece, counted in
    tokens of the sentence they came from -- which is how each piece
    finds its own times later.
    """
    out: list[tuple[str, int, int]] = []
    cur, lo, pos = [], tokens_before, tokens_before
    for atom in atoms:
        n = len(_key(atom))
        joined = " ".join(cur + [atom])
        wide = (len(joined) > CAPTION_CHARS
                or len(joined.split()) > CAPTION_WORDS)
        slow = span(lo, pos + n) > CAPTION_SECONDS
        if cur and (wide or slow):
            out.append((" ".join(cur), lo, pos))
            cur, lo = [], pos
        cur.append(atom)
        pos += n
    if cur:
        out.append((" ".join(cur), lo, pos))
    return out


def _by_breath(text: str, lo: int, hi: int, at) -> list[tuple[str, int, int]]:
    """A clause still too long on its own, cut where the speaker breathed.

    Same rule as `_breath` uses on an unscripted take: the widest silence
    beats whatever word a counter happened to reach.
    """
    words = text.split()
    if len(text) <= CAPTION_CHARS and len(words) <= CAPTION_WORDS:
        return [(text, lo, hi)]

    # A written word is not always one token: `_key` splits
    # "decision-maker" into two and "can't" into two, so the count of
    # things on the page and the count of things matched against the
    # transcript drift apart. Comparing them directly made this function
    # give up silently -- which is how a seventy-three character, seven
    # second caption reached the screen with both ceilings in place.
    steps = [len(_key(w)) for w in words]
    offset = [lo + sum(steps[:i]) for i in range(len(words) + 1)]
    if offset[-1] != hi:
        return [(text, lo, hi)]           # genuinely cannot line them up

    # Only the places that leave a full first caption are worth
    # considering at all -- a break is a choice between good places, not
    # a licence to put four words on screen and nine on the next one.
    fits = [i for i in range(BREATH_MIN_WORDS,
                             len(words) - BREATH_MIN_WORDS + 1)
            if len(" ".join(words[:i])) <= CAPTION_CHARS]
    if not fits:
        fits = [max(BREATH_MIN_WORDS, len(words) // 2)]

    best, cut = 0.0, 0
    for i in fits:
        a, b = at(offset[i] - 1), at(offset[i])
        gap = (b[0] - a[1]) if a and b else 0.0
        if gap > best:
            best, cut = gap, i
    # A real breath wins. Below that the "widest" silence is noise --
    # measured on a take where the winning gap was 0.00s, which cut
    # "He was pulling fresh | readings from weather balloons" for no
    # reason at all. With nothing to go on, fill the line instead.
    if best < REAL_BREATH or not cut:
        cut = fits[-1]
    return (_by_breath(" ".join(words[:cut]), lo, offset[cut], at)
            + _by_breath(" ".join(words[cut:]), offset[cut], hi, at))


def align_to_script(words: list, units: list[str]) -> list[Line]:
    """Give each written sentence the times of the words that said it.

    `words` is whisper's word list; `units` is `script_units`. Returns one
    Line per sentence that was actually spoken, timed from the transcript
    and worded from the script.

    A sentence read twice keeps the LAST reading, which is what a person
    means by reading it twice.
    """
    spoken, spoken_at = [], []
    for i, w in enumerate(words):
        for tok in _key(getattr(w, "word", "")):
            spoken.append(tok)
            spoken_at.append(i)

    written, written_unit, written_pos = [], [], []
    for u, unit in enumerate(units):
        for j, tok in enumerate(_key(unit)):
            written.append(tok)
            written_unit.append(u)
            written_pos.append(j)

    if not spoken or not written:
        return []

    # Which spoken word each written word turned out to be.
    pairs: dict[int, list[tuple[int, int]]] = {}
    sm = difflib.SequenceMatcher(None, written, spoken, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            pairs.setdefault(written_unit[a + k], []).append(
                (written_pos[a + k], b + k))

    out: list[Line] = []
    for u, unit in enumerate(units):
        got = sorted(pairs.get(u, []), key=lambda p: p[1])
        if not got:
            continue                      # written but never said
        # Keep only the last run. Two runs far apart is the same
        # sentence read twice, and the good one is the one you kept
        # going after.
        run = [got[-1]]
        for pair in reversed(got[:-1]):
            if run[0][1] - pair[1] > FALSE_START_GAP:
                break
            run.insert(0, pair)
        when = {pos: words[spoken_at[j]] for pos, j in run}

        def at(pos, _when=when):
            w = _when.get(pos)
            return (float(w.start), float(w.end)) if w else None

        def span(lo, hi, _when=when):
            """How long the words from lo to hi took to say."""
            here = [_when[p] for p in range(lo, hi) if p in _when]
            return (float(here[-1].end) - float(here[0].start)) if here else 0.0

        # Cut at your own commas and dashes first; anything still too
        # long gets cut where you breathed.
        pieces: list[tuple[str, int, int]] = []
        for text, lo, hi in _pack(_atoms(unit), span, 0):
            pieces += _by_breath(text, lo, hi, at)

        for text, lo, hi in pieces:
            here = [when[p] for p in range(lo, hi) if p in when]
            if not here:
                continue                  # this clause was never said
            out.append(Line(text, float(here[0].start), float(here[-1].end)))

    # Times must not run backwards, whatever the matcher decided.
    out.sort(key=lambda ln: ln.start)
    return out


def lines_for(words: list, script: str | None) -> list[Line]:
    """The captions for one stretch of speech.

    Uses the script when there is one and it was actually followed; falls
    back to listening when there is not, or when what was said has
    drifted too far from what was written for the alignment to mean
    anything.
    """
    units = script_units(script or "")
    if not units:
        return _chunk_words(words)
    aligned = align_to_script(words, units)
    heard = len([t for w in words for t in _key(getattr(w, "word", ""))])
    said = sum(len(_key(ln.text)) for ln in aligned)
    # Under half of what was said accounted for by the script means this
    # take went its own way. Trust the ears, not the page.
    if not aligned or heard and said / heard < 0.5:
        return _chunk_words(words)
    return aligned


def _model_cached(model_size: str) -> bool:
    """Has this model already been downloaded? Only used to decide whether
    to warn about a long wait -- being wrong costs nothing."""
    home = os.environ.get("HF_HOME")
    root = Path(home) / "hub" if home else Path.home() / ".cache" / "huggingface" / "hub"
    repo = root / f"models--Systran--faster-whisper-{model_size}"
    # The folder appears the moment a download starts, so its existence
    # proves nothing. The weights file is the thing.
    return any(repo.glob("snapshots/*/model.bin"))


def transcribe(audio: Path, model_size: str = "small",
               language: str | None = None,
               script: str | None = None) -> list[Line]:
    """Speech -> a list of short lines, each with a start and end time.

    Whisper segments speech into breath-sized chunks; `_chunk_words`
    then splits those further at real punctuation so no caption on
    screen outstays a natural pause.
    """
    # The guard in cli.cmd_caption imports THIS module, which succeeds --
    # faster_whisper is only reached here, lazily. So the friendly message
    # has to live at the point of use, or a clip with talking in it ends
    # the run with a raw ModuleNotFoundError.
    # huggingface_hub is chatty on Windows, and everything it says here is
    # noise you cannot act on: that it could not make symlinks (true, and
    # harmless -- it just uses a little more disk), and that the download
    # is unauthenticated (true, and irrelevant for a public model). Both
    # arrive mid-run looking like errors. Quiet them before the import
    # that triggers them.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

    # Fetch the model over plain HTTP rather than Xet, huggingface's newer
    # chunked transfer. Xet is faster when it works and dies with a
    # "CAS Client Error" when it does not -- which it does on plenty of
    # ordinary connections, and the traceback it leaves is meaningless to
    # anyone. This is a one-time download of a few hundred MB; boring and
    # reliable beats fast. Set HF_HUB_DISABLE_XET=0 yourself to opt back in.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "Putting your talking on screen needs one extra package that "
            "isn't installed by default (about 100 MB, which is why it is "
            "optional). Install it once:\n\n"
            "    uv sync --extra voice\n\n"
            "then run the same command again. Everything else works without "
            "it -- add --no-captions to skip this and carry on now."
        )

    if _model_cached(model_size):
        print(f"  loading the {model_size} speech model ...")
    else:
        print(f"  fetching the {model_size} speech model. This happens once,")
        print(f"  it is a few hundred MB, and it can take several minutes on")
        print(f"  a slow connection. Nothing is wrong -- let it finish.")
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:
        # Almost always the download, and almost always the network. The
        # cache resumes, so running it again really is the right advice.
        raise SystemExit(
            f"Could not load the {model_size} speech model.\n\n"
            f"  {type(e).__name__}: {str(e)[:300]}\n\n"
            f"If that mentions a download, a connection or a CAS error, it "
            f"is the fetch that failed, not your film. What already came "
            f"down is kept, so just run the same command again -- it picks "
            f"up where it stopped. A smaller model downloads sooner:\n\n"
            f"    uv run film caption --model base\n\n"
            f"Everything else works without captions in the meantime."
        )

    print(f"  listening to {audio.name} ...")
    segments, info = model.transcribe(str(audio), vad_filter=True,
                                      word_timestamps=True,
                                      language=language)

    # Whisper hands back breath-sized segments. Chunking by ear works on
    # one of those at a time, but MATCHING A SCRIPT cannot: a sentence
    # you wrote often takes two breaths to say, and aligning each segment
    # on its own found that sentence in both of them and captioned it
    # twice. Measured on a real take: 4 of 23 sentences came out doubled.
    # So the script path sees the whole take at once, and the listening
    # path is left exactly as it was.
    following_a_script = bool(script_units(script or ""))
    lines: list[Line] = []
    every_word: list = []
    for seg in segments:
        words = list(seg.words or [])
        if not words:
            t = seg.text.strip()
            if t:
                lines.append(Line(t, seg.start, seg.end))
            continue
        every_word.extend(words)
        if not following_a_script:
            lines.extend(_chunk_words(words))

    if following_a_script and every_word:
        lines.extend(lines_for(every_word, script))
    lines.sort(key=lambda ln: ln.start)

    print(f"  {len(lines)} lines, language detected: {info.language}")
    return lines


def save_transcript(project: Path,
                    sources: list[tuple[str, list[Line]]]) -> Path:
    """A plain, readable side file -- edit the wording here before
    pulling lines into film.yaml. Never auto-applied without review.
    `sources` is [(label, lines), ...] -- one entry per audio source."""
    out = project / "analysis" / "transcript.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "sources": [
            {"source": label,
             "lines": [{"text": ln.text, "start": round(ln.start, 2),
                       "end": round(ln.end, 2)} for ln in lines]}
            for label, lines in sources
        ]
    }
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def transcript_readable(project: Path,
                        sources: list[tuple[str, list[Line]]]) -> Path:
    """A .txt companion -- easiest place to just read what was captured."""
    out = project / "analysis" / "transcript.txt"
    blocks = []
    for label, lines in sources:
        rows = [f"[{ln.start:6.2f} - {ln.end:6.2f}]  {ln.text}" for ln in lines]
        blocks.append(f"-- {label} --\n" + "\n".join(rows))
    out.write_text("\n\n".join(blocks), encoding="utf-8")
    return out
