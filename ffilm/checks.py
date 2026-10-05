"""
checks.py  --  what is wrong with a film, found before the render finds it.

`film check`, `film go` and the preflight all ask these questions; the
command line only prints the answers. Kept apart from cli.py so each
check is a function a test can call with a folder and a Film -- which is
how every one of them is tested.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from . import cover, kinds, library, voice
from .spec import VOICE_TAIL


def voice_installed() -> bool:
    """Is the optional speech model package there?"""
    from importlib.util import find_spec
    try:
        return find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


def speed_to_fit(film, target: float, max_speed: float) -> float | None:
    """The one `speed:` for every sped-up shot that brings the film to
    `target` seconds, rounded UP to two decimals. Pure. For `film fit`.

    The shots whose length comes from their speed (a take, a narrated
    picture) are the part that scales: (out - in) / speed. Everything
    else is fixed -- the opening card, silent photographs, a `duration:`
    hold, and the breath after a narrated picture (VOICE_TAIL). Then
    spoken / (target - fixed) is the speed.

    A film that already fits gets its current speed back. None means it
    cannot be done by speed: nothing to speed up, the fixed part alone
    overruns the target, or the answer is above `max_speed`.
    """
    fixed = spoken = 0.0
    current = 1.0
    for s in film.shots:
        tail = VOICE_TAIL if s.voice else 0.0
        if (abs(s.speed - 1.0) > 1e-3 and s.tout is not None
                and abs(s.duration - ((s.tout - s.tin) / s.speed + tail)) < 1e-6):
            spoken += s.tout - s.tin
            fixed += tail
            current = max(current, s.speed)
        else:
            fixed += s.duration
    if not spoken:
        return None
    if film.duration <= target:
        return current
    room = target - fixed
    if room <= 0:
        return None
    needed = math.ceil(spoken / room * 100 - 1e-9) / 100
    return needed if needed <= max_speed else None


def shot_lines(film) -> list[str]:
    """One line per shot for `film check`. Pure.

    A slide says which words it is holding. Without that the listing
    showed a photograph and a length and nothing else, so the only way
    to see what a shot was quoting was to open film.yaml -- and the
    whole point of `check` is answering that without opening anything.
    """
    out = []
    for s in film.shots:
        caps = f"  {len(s.captions)} caption(s)" if s.captions else ""
        words = ""
        if s.voice:
            words = (f"  <- voice {_clock(s.tin)}-"
                     f"{_clock(s.tout if s.tout is not None else s.tin + s.duration)}")
        out.append(f"  {s.id}  {s.duration:5.1f}s  {s.move:<12} "
                   f"{s.src}{words}{caps}")
    return out


def _clock(seconds: float) -> str:
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f"{int(m):02d}:{s:05.2f}"


def unused_media(project: Path, film) -> list[str]:
    """Files in media/ that no shot in the film uses.

    The single worst thing this toolkit can do is leave something of
    yours out and say nothing, and until now nothing checked. `ingest`
    reports what it could not READ; nothing reported what it read fine
    and then never put on screen -- which is what happens to a photograph
    you dropped in after `init` had already written the edit, or to one
    you numbered `13_` in a film whose numbering stops at 12.
    """
    media = project / "media"
    if not media.is_dir():
        return []
    used = set()
    for s in film.shots:
        used.add(Path(s.src).name.lower())
        # A shot may point at a proxy or at a converted HEIC; both are
        # named for the original, so the stem is what identifies it.
        used.add(Path(s.src).stem.lower())
    out = []
    for p in sorted(media.rglob("*")):
        if not p.is_file() or kinds.is_aside(p, media):
            continue
        if p.suffix.lower() not in kinds.MEDIA:
            continue
        if p.name.lower() in used or p.stem.lower() in used:
            continue
        out.append(p.relative_to(project).as_posix())
    return out


# A wide clip in a tall frame keeps 32% of its width. That is fine on a
# landscape with room to lose and wrong on a face, and `fill: blur`
# already exists for exactly this -- it just had no way of being
# suggested. Only worth saying when the subject is near an edge, because
# that is when cropping actually takes part of them away.
EDGE = 0.28


def framing_notes(film) -> list[str]:
    """Where the crop is about to cost something, said before the render.

    Everything needed for this was already on the shot -- the frame's
    shape, the clip's shape, the focus point -- and nothing put the three
    together, so `fill: blur` was a feature you had to already know about
    to find.
    """
    if film.height <= film.width:
        return []                      # a tall picture in a wide frame is fine
    out = []
    for s in film.shots:
        if s.kind != "video" or (s.fill or film.fill) == "blur":
            continue
        try:
            src = film.resolve(s.src)
            import cv2
            cap = cv2.VideoCapture(str(src))
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            cap.release()
        except Exception:
            continue
        if not w or not h or w <= h:
            continue
        fx = (s.focus or (0.5, 0.5))[0]
        if EDGE < fx < 1.0 - EDGE:
            continue
        out.append(
            f"[{s.id}] a {int(w)}x{int(h)} clip in a {film.width}x"
            f"{film.height} frame keeps about "
            f"{100 * (film.width / film.height) / (w / h):.0f}% of its "
            f"width, and the subject is at {fx:.2f} -- near the edge that "
            f"gets cut off.")
    if out:
        out.append("    Add `fill: blur` at the top of film.yaml to keep "
                   "the picture whole")
        out.append("    on a blurred copy of itself instead of cropping it.")
    return out


def bokeh_notes(film) -> list[str]:
    """A film that asks for bokeh without the model file, said at check
    time rather than half way into a render. See segment.missing_model."""
    from . import segment
    if not any(film.bokeh_for(s) > 0 for s in film.shots):
        return []
    msg = segment.missing_model()
    return msg.splitlines() if msg else []


_ASK = object()


def depth_notes(film, runner=_ASK, model_present=_ASK) -> list[str]:
    """Which photographs get parallax, and whether this computer can give
    it. `runner` is depth.missing_runner()'s answer and `model_present`
    whether the model file is there; both are looked up when not given."""
    from . import depth, models
    shots = [s.id for s in film.shots if film.depth_for(s) > 0]
    if not shots:
        return []
    if runner is _ASK:
        runner = depth.missing_runner()
    if model_present is _ASK:
        model_present = models.is_present(models.DEPTH)
    out = [f"depth (parallax) on {len(shots)} photo(s): {', '.join(shots)}"]
    if runner:
        out.append("  Not on this computer yet -- they will render flat:")
        out += [f"  {line}" for line in runner.splitlines()]
    elif not model_present:
        out.append(f"  The model {models.DEPTH.file} "
                   f"({models.DEPTH.size // 1_000_000} MB) downloads on the "
                   f"first render, or now: uv run film models")
    return out


def film_shape(project: Path) -> tuple[int, int]:
    """The film's own resolution, read cheaply. Not Film.load, which
    validates every source file -- a cover should still build for a film
    whose footage is on a drive that is not plugged in."""
    from .spec import headers
    res = headers(project / "film.yaml").get("resolution")
    try:
        if res and len(res) == 2:
            return int(res[0]), int(res[1])
    except (ValueError, TypeError):
        pass
    if (project / ".vertical").exists():
        return 1080, 1920
    return cover.WIDE


def preflight_report(project: Path) -> tuple[list[str], list[str]]:
    """The checks, as (what is fine, what is in the way). Separated from
    the printing so that a caller which needs both the answer and the
    text does not have to run every check twice to get them."""
    import shutil as _shutil
    from .ingest import faces_available

    lines, problems = [], []

    # Not a problem -- nothing fails and every film still renders -- but
    # it is a capability the toolkit used to claim and silently stopped
    # having, so it says so rather than letting you wonder why a portrait
    # is framed on the bookshelf behind you.
    if faces_available():
        lines.append("  ok    face detection (photos framed on the face)")
    else:
        lines.append("  --    no face detection in this OpenCV: photos are "
                     "framed on\n        detail instead. Clips are unaffected "
                     "-- they find the speaker\n        by motion.")

    for tool in ("ffmpeg", "ffprobe"):
        if _shutil.which(tool):
            lines.append(f"  ok    {tool}")
        else:
            problems.append(
                f"{tool} is not installed, or this window was opened before "
                f"it was. Close every terminal, open a new one, and try "
                f"again. If that does not help:  "
                f"winget install --id Gyan.FFmpeg -e")

    media = project / "media"
    files = [p for p in media.rglob("*")
             if p.is_file() and p.suffix.lower() in kinds.MEDIA
             ] if media.is_dir() else []
    if files:
        stills = sum(1 for p in files
                     if p.suffix.lower() in kinds.STILL | kinds.HEIC)
        lines.append(f"  ok    {len(files)} files in media  "
                     f"({stills} photos, {len(files) - stills} clips)")
    else:
        problems.append(f"nothing to edit yet -- put photos or clips in {media}")

    lines.extend(library_lines(project))

    try:
        free = _shutil.disk_usage(project).free / 1e9
        if free < 2:
            problems.append(f"only {free:.1f} GB free on this drive. Rendering "
                            f"needs room for a temporary copy of the film.")
        else:
            lines.append(f"  ok    {free:.0f} GB free")
    except OSError:
        pass

    lines.append("  ok    captions available" if voice_installed()
                 else "  --    captions off (uv sync --extra voice turns them on)")
    from .models import status_lines
    lines.extend(status_lines())
    return lines, problems


def library_lines(project: Path) -> list[str]:
    """Where this film's music and thumbnail picture are coming from.

    Two lines, and each one names the folder, because the whole promise
    of the shelf is that you can fix either of them by dropping a file
    somewhere -- which is no use if you cannot see which somewhere.
    """
    from .spec import find_music

    out = []
    track = find_music(project)
    if track is None:
        out.append("  --    no music yet. Put one file in the folder below "
                   "and every")
        out.append("        film you make from now on has it:")
        out.append(f"          {library.music_dir()}")
    else:
        where = Path(track)
        # An absolute path can only have come off the shelf: a track in
        # this film's own folder is stored relative to it.
        out.append(f"  ok    music: {where.name}"
                   + ("   (your library -- every film gets it)"
                      if where.is_absolute() else "   (this film's own)"))

    w, h = film_shape(project)
    back = cover.choose(project, wide=w >= h)
    if back.path is None:
        out.append("  --    no thumbnail picture yet. Put a wide one and a "
                   "tall one here")
        out.append("        and every film gets a cover of its own shape:")
        out.append(f"          {library.cover_dir()}")
    else:
        out.append(f"  ok    thumbnail picture: {back.name}"
                   + ("   (your library)" if back.shared
                      else "   (this film's own)"))
        note = shape_note(library.is_wide(back.path), w >= h)
        if note:
            out.append(note)
    return out


def shape_note(picture_wide: bool | None, film_wide: bool) -> str | None:
    """A cover picture the wrong shape for the film. Pure.

    It is never letterboxed, on purpose, so it is cropped -- and a
    portrait on a wide film keeps a band across the middle. On "Prayer for
    Her" that band cut the face off, and nothing said so until the
    thumbnail was looked at.
    """
    if picture_wide is None or picture_wide == film_wide:
        return None
    if film_wide:
        return ("        a portrait picture on a wide film: its top and "
                "bottom are cropped.\n"
                "        A wide one in cover\\ would fit the frame.")
    return ("        a landscape picture on a tall film: its sides are "
            "cropped.\n"
            "        A tall one in cover\\ would fit the frame.")


def music_note(m, total: float) -> str | None:
    """What the check says about a track shorter than the film. Pure.

    A track that runs out used to be joined to itself with nothing
    between -- dead air, 3:08 into "I am not your fear". It is repeated
    with a crossfade now, and a repeat is something you might still want
    to know about before you hear it: a song with words, restarting.
    """
    from .audio import music_plan
    plan = music_plan(m.head, m.tail, total, m.length)
    if plan.repeats <= 1:
        return None
    usable = m.tail - m.head
    times = {2: "once", 3: "twice"}.get(plan.repeats,
                                          f"{plan.repeats - 1} times")
    line = (f"  --    {usable:.0f}s of music under a {total:.1f}s film: "
            f"it repeats {times}, crossfaded")
    if plan.short_by > 0.5:
        line += (f", and stops {plan.short_by:.0f}s before the end. "
                 f"A longer track fixes that")
    return line


def music_notes(film) -> list[str]:
    """The music line for `film check`, measured (once, cached)."""
    from .audio import measure_music
    if not film.music:
        return []
    track = film.resolve(film.music)
    if not track.exists():
        return []
    note = music_note(measure_music(track, film.root / "analysis"),
                      film.duration)
    return [note] if note else []


def narration_note(audio_seconds: float, film_seconds: float) -> str | None:
    """What to say when a separately-recorded narration (`audio:`) runs
    past the end of the pictures it plays under. Pure.

    audio.build_soundtrack's last filter is `apad,atrim=0:total` -- a
    narration longer than the film is silently cut to fit, with nothing
    said about it anywhere. A narration that ends in silence, with no
    warning, was judged the worst outcome on the 2026-09-17 plan's list.
    """
    over = audio_seconds - film_seconds
    if over <= 0.5:
        return None
    return (f"  --    {audio_seconds:.0f}s of narration under a "
            f"{film_seconds:.1f}s film: the last {over:.0f}s will not be "
            f"heard. Hold the photographs longer, or "
            f"`film go --target {audio_seconds:.0f}`")


def narration_seconds_in_film(recording: float, offset: float) -> float:
    """Where the narration ends on the film's clock. Pure. A positive
    `audio_offset` is a wait before it starts; a negative one skips that
    much of the recording's start."""
    return recording + offset


def narration_notes(film) -> list[str]:
    """The narration line for `film check` and the render, measured off
    the file `audio:` points at."""
    from .audio import _dur
    if not film.audio:
        return []
    path = film.resolve(film.audio)
    if not path.exists():
        return []
    note = narration_note(narration_seconds_in_film(_dur(path),
                                                    film.audio_offset),
                          film.duration)
    return [note] if note else []


# The editor's rulebook keeps captions under about a fifth of the runtime.
CAPTION_SHARE_TASTE = 0.20


def caption_share_line(film) -> str | None:
    """How much of the film has words on screen. Pure.

    A talking film captioned word for word is far over the taste rule,
    and that may be exactly right for a Short watched with the sound
    off -- so this says the number and does not decide.
    """
    total = sum(s.duration for s in film.shots)
    shown = sum(min(c.dur, max(0.0, s.duration - c.at))
                for s in film.shots for c in s.captions)
    if total <= 0 or shown <= 0:
        return None
    share = shown / total
    if share <= CAPTION_SHARE_TASTE:
        return f"  ok    captions: {share:.0%} of the runtime"
    return (f"  --    captions: {share:.0%} of the runtime, over the "
            f"{CAPTION_SHARE_TASTE:.0%} taste rule. Right for a film "
            f"watched muted; cut the ones that repeat the picture otherwise")


# A caption has to be on screen long enough to read. Two numbers, because
# one clause alone gets it wrong in one direction or the other.
#
# Under this many seconds is worth a look at all...
CAPTION_MIN_READ = 1.2
# ...but only if it is also faster per word than anybody can speak.
#
# This number was measured, not chosen. Run at 0.30 s/word across all 19
# films in projects/, it flagged 41 captions, and most were fine: "That
# is the tradition." at 1.04s is 3.8 words/sec, which is fast and
# sayable, and `stop_overlap` SHORTENS a caption on purpose so it does
# not collide with the next -- so a short `dur` is very often correct.
#
# Jacek speaks at 97-110 wpm, about 0.45-0.51 s/word played. 0.15 s/word
# is 400 wpm, past any human. The four captions that shipped invisible on
# 2026-09-21 were at 0.026-0.097, an order of magnitude under it; the
# shortest correct line in the whole repo is 0.24. Nothing sits between.
CAPTION_MIN_PER_WORD = 0.15


def unreadable_captions(film) -> list[str]:
    """Captions that cannot be read in the time they are given. Pure.

    Found 2026-09-21, after a film was published with an invisible
    intro. The transcriber returned the right words for a take and junk
    times for them -- 0.26s for a ten-word sentence -- and `film caption`
    placed them on the spans it was handed. Nothing said the spans were
    impossible, so `check` printed OK and the only way to find out was to
    watch a draft.

    The second clause catches the same fault when the duration survives
    it: a line whose `words:` holds one time out of ten was not heard,
    whatever its span says. The rule is the `fix-captions` skill's, which
    had been written down for two days and was never code.
    """
    out = []
    for s in film.shots:
        for c in s.captions:
            n = len(c.text.split())
            if n == 0:
                continue
            why = []
            unreadable = (c.dur < CAPTION_MIN_READ
                          and c.dur / n < CAPTION_MIN_PER_WORD)
            if unreadable:
                why.append(f"{c.dur:.2f}s for {n} words")
            if c.words and len(c.words) * 2 < n:
                why.append(f"{len(c.words)} of {n} word times")
            if not why:
                continue
            # Two different faults, and saying "nobody can read" about
            # both would be untrue. A caption placed by hand on the
            # measured speech is on screen for five seconds and perfectly
            # readable; what is still wrong with it is that the highlight
            # has one word time to follow. Bauhaus's two German titles are
            # exactly that, and they were fixed and accepted on
            # 2026-09-19. Telling Jacek they are unreadable would send him
            # back to something already settled.
            head = ("a caption nobody can read" if unreadable
                    else "a caption whose highlight cannot follow the words")
            out.append(f"[{s.id}] {head} -- {'; '.join(why)}: \"{c.text}\"")
    if out:
        out.append("    The words are probably right and the TIMES are "
                   "wrong. See the")
        out.append("    fix-captions skill: place them on the speech "
                   "measured in the audio.")
        out.append("    A line the transcriber only half heard cannot get "
                   "its highlight back;")
        out.append("    that one is worth knowing about and not worth "
                   "fixing by hand.")
    return out


# A repeat is only worth saying when the line is long enough to be a real
# one. Short lines recur on purpose -- a refrain, a title, a two-word
# answer -- and flagging those would train you to ignore this.
REPEAT_MIN_WORDS = 3


def _said(text: str) -> str:
    """The words of a caption, as words. Case, spacing, punctuation and
    the arrows in a diagram line are not part of what was said."""
    return " ".join(re.findall(r"\w+", text.casefold()))


# Words that carry no content of their own, so sharing them proves
# nothing. Short on purpose: a word left out of here only makes the check
# more cautious, never noisier, because the rule also asks for SAME_WORDS.
_FILLER = set("""a an the and or but so of to in on at by for with from as is
    are was be it its this that these those then than into up out no not
    every each one two do does did has have had you your we our they their
    i""".split())

# Three captions against three. Measured on every film in projects/
# (2026-10-05): one sentence against one cannot tell a paraphrase from
# chance -- both scored 0.67 on SUMIFS. Three can: SUMIFS's closing that
# re-said its intro scored 0.78 with 7 shared words, the best unrelated
# passage 0.50; over 20 films, 3 other passages reached the line.
PARAPHRASE_SPAN = 3
PARAPHRASE_SHARE = 0.6     # of the shorter passage's content words
SAME_WORDS = 5             # and at least this many of them


def _content(text: str) -> set[str]:
    """A caption's content words: lower case, no filler, a plural `s`
    dropped so `filters` and `filter` count as one word."""
    out = set()
    for w in re.findall(r"\w+", text.casefold()):
        if w in _FILLER:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def paraphrased_captions(film) -> list[str]:
    """Passages the film says twice in other words, and where. Pure.

    repeated_captions finds the same words. This finds the same CONTENT:
    on SUMIFS SUMPRODUCT vs DAX the closing take re-said the intro --
    "SUMIFS adds by condition" came back as "SUMIFS adds one column by
    condition", and so on for three sentences -- and only reading found
    it. Every run of PARAPHRASE_SPAN captions inside one shot is compared
    with every run in every other shot; a pair of shots is named once, at
    its closest passages. Like the exact check, this says where and
    decides nothing: an outro that sums up on purpose is not a fault.
    """
    runs = []
    t = 0.0
    for s in film.shots:
        caps = s.captions
        for i in range(len(caps) - PARAPHRASE_SPAN + 1):
            part = caps[i:i + PARAPHRASE_SPAN]
            words = set().union(*(_content(c.text) for c in part))
            runs.append((s.id, t + part[0].at, words,
                         " / ".join(c.text for c in part)))
        t += s.duration or 0.0
    best: dict[tuple[str, str], tuple] = {}
    for n, a in enumerate(runs):
        for b in runs[n + 1:]:
            if a[0] == b[0] or not a[2] or not b[2]:
                continue
            same = a[2] & b[2]
            share = len(same) / min(len(a[2]), len(b[2]))
            if share < PARAPHRASE_SHARE or len(same) < SAME_WORDS:
                continue
            key = (a[0], b[0])
            if key not in best or share > best[key][0]:
                best[key] = (share, a, b)
    # The first and last shots that speak are the intro and the closing.
    # A closing that reminds people of the intro is often meant (Jacek,
    # 2026-10-05), so that pair is named as a recap, not as a repeat.
    spoken = [s.id for s in film.shots if s.captions]
    ends = (spoken[0], spoken[-1]) if len(spoken) > 1 else None
    out = []
    for share, a, b in best.values():
        what = ("the closing recaps the intro -- fine if it is a reminder, "
                "a cut if not" if (a[0], b[0]) == ends
                else "the same thing said in other words")
        out.append(f"{what} ({share:.0%} of the content words) -- "
                   f"{a[0]} at {_clock(a[1])} and {b[0]} at {_clock(b[1])}:")
        out.append(f'      "{a[3]}"')
        out.append(f'      "{b[3]}"')
    if out:
        out.append("    Found by shared words, not by meaning: read both "
                   "before cutting.")
        out.append("    A closing that sums up on purpose is not a fault. "
                   "Cutting one is")
        out.append("    the fit-to-length skill: whole sentences, never "
                   "half of one.")
    return out


def repeated_captions(film) -> list[str]:
    """Lines the film says more than once, and where. Pure.

    Found 2026-09-21, twice in one film. `init` put one take in as the
    intro and the WHOLE of a second take in as the closing, and the
    second take re-read the intro -- so the film said those four
    sentences at 0:02 and again at 2:20. That one was caught by reading
    film.yaml. The other was not: a shot showed and SAID its line at 1:40
    and again at 1:44, and the film was published that way.

    `fit-to-length` exists as a skill for cutting what a film says twice.
    Nothing ever looked. The captions are the film's own record of what
    is said, so this is a dictionary.
    """
    where: dict[str, list[tuple[str, float, str]]] = {}
    order: list[str] = []
    t = 0.0
    for s in film.shots:
        for c in s.captions:
            key = _said(c.text)
            if len(key.split()) < REPEAT_MIN_WORDS:
                continue
            if key not in where:
                where[key] = []
                order.append(key)
            where[key].append((s.id, t + c.at, c.text))
        t += s.duration or 0.0
    out = []
    for key in order:
        places = where[key]
        if len(places) < 2:
            continue
        how = "twice" if len(places) == 2 else f"{len(places)} times"
        spots = " and ".join(f"{sid} at {_clock(at)}" for sid, at, _ in places)
        out.append(f'the same words said {how} -- {spots}: "{places[0][2]}"')
    if out:
        out.append("    You may have read a line again and kept both takes. "
                   "The sound")
        out.append("    repeats as well as the caption, and so does "
                   "upload.txt. Cutting")
        out.append("    one is the fit-to-length skill: drop the whole "
                   "sentence, never split it.")
        out.append("    A refrain you meant is not a fault. Nothing here "
                   "can tell the two")
        out.append("    apart, so this says where they are and decides "
                   "nothing.")
    return out


def half_captioned(scripts: list[str], film) -> list[str]:
    """Sentences of the script with some clauses on screen and some not. Pure.

    Found 2026-09-28 on What Is Love: "In one study," and "A 2018
    meta-analysis by Kathrin Karsay," were said and never captioned. The
    matcher had taken misheard names for a false start (voice._misheard
    has the story), and `check` printed OK, because it only ever read
    the captions that were there.

    A sentence with NONE of its clauses on screen is not named: it was
    cut whole on purpose (fit-to-length) or not recorded yet. Half a
    sentence is never on purpose. Captions are read as one run of words,
    so a clause broken across two captions still counts as there.

    A clause under REPEAT_MIN_WORDS says nothing either way. Swept over
    all 22 films: "kitchen," and "WC," of a Bauhaus sentence were found
    inside another caption, and made a sentence nobody captioned look
    half there.
    """
    shown = " " + " ".join(voice._key(" ".join(
        c.text for s in film.shots for c in s.captions))) + " "
    out = []
    for script in scripts:
        for unit in voice.script_units(script):
            clauses = [a.strip() for a in voice._atoms(unit)
                       if len(voice._key(a)) >= REPEAT_MIN_WORDS]
            there = [f" {' '.join(voice._key(a))} " in shown for a in clauses]
            if any(there) and not all(there):
                gone = " / ".join(f'"{a}"' for a, ok in zip(clauses, there)
                                  if not ok)
                out.append(f"half a sentence on screen -- not in any "
                           f"caption in these words: {gone}")
    if out:
        out.append("    The rest of the sentence is captioned, so this "
                   "was said too.")
        out.append("    See the fix-captions skill: place it on the "
                   "speech measured in the audio.")
    return out
