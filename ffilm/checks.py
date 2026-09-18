"""
checks.py  --  what is wrong with a film, found before the render finds it.

`film check`, `film go` and the preflight all ask these questions; the
command line only prints the answers. Kept apart from cli.py so each
check is a function a test can call with a folder and a Film -- which is
how every one of them is tested.
"""

from __future__ import annotations

from pathlib import Path

from . import cover, kinds, library


def voice_installed() -> bool:
    """Is the optional speech model package there?"""
    from importlib.util import find_spec
    try:
        return find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


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
