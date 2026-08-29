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

import json
import logging
import os
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


def _chunk_words(words: list, max_words: int = 12) -> list[Line]:
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
        elif word_text.endswith(",") and len(chunk) >= 5:
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
               language: str | None = None) -> list[Line]:
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

    lines: list[Line] = []
    for seg in segments:
        words = list(seg.words or [])
        if not words:
            t = seg.text.strip()
            if t:
                lines.append(Line(t, seg.start, seg.end))
            continue
        lines.extend(_chunk_words(words))

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
