"""
cli.py  --  the commands you type.

    uv run film                     "what do I do next?" -- it walks you
                                    through, one step at a time. Start here
                                    if you do not remember the rest.

    uv run film ingest              look at the media, build the contact sheet
    uv run film peek                ~seconds   is the ORDER right?
    uv run film draft               ~a minute  does the MOTION feel right?
    uv run film final               minutes    ship it

    uv run film init                write a first film.yaml automatically
    uv run film edit                open the editing bench in your browser
    uv run film new <name>          start a new project folder
    uv run film check               validate film.yaml without rendering
    uv run film library             the music + cover pictures every film uses
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dataclasses import replace

from . import cover
from . import ingest as ingest_mod
from . import kinds
from . import library
from . import editor
from . import guide
from . import history
from . import scaffold
from .moves import choose_moves
from .render import QUALITIES, render
from .spec import Film

DEFAULT_PROJECT = "projects/film_001"


def toolkit_root() -> Path:
    """Where ffilm itself lives, no matter which folder the terminal is in."""
    return Path(__file__).resolve().parent.parent


def find_project(arg: str | None) -> Path:
    """Find the project folder without requiring `cd` into AI-Film first.

    If you did not pass -p, and the folder you are standing in already
    looks like a project (has media/ or film.yaml), we use THAT folder --
    this is what makes `uv run film ingest` work with no arguments when
    you are sitting inside your own project directory in RStudio.

    Only if that fails do we fall back to interpreting the name as
    relative to AI-Film's own projects/ folder.
    """
    cwd = Path.cwd()
    if arg is None and ((cwd / "media").is_dir() or (cwd / "film.yaml").exists()):
        return cwd.resolve()

    given = arg or DEFAULT_PROJECT
    p = Path(given)

    candidates = [cwd] if arg is None else []
    candidates.append(p)
    if not p.is_absolute():
        candidates.append(toolkit_root() / p)
        candidates.append(toolkit_root() / "projects" / p.name)

    for c in candidates:
        if (c / "media").is_dir() or (c / "film.yaml").exists():
            return c.resolve()

    raise SystemExit(
        f"No project found for {given!r}.\n"
        f"Looked in:\n" + "\n".join(f"  - {c}" for c in candidates) +
        f"\n\nIf this is a brand new project, create it first:\n"
        f"  uv run film new {p.name or 'my_movie'}\n"
        f"...or make sure it has a media\\ subfolder with your photos in it."
    )


# Every folder a project has, made together, always. cover/ and music/
# are made even though most films use the shared shelf instead: an empty
# folder with a known name is where you put the exception, and finding
# somewhere to put the exception should not need a manual.
PROJECT_DIRS = ("media", "music", "cover", "analysis", "out")


def make_project(root: Path, vertical: bool = False) -> Path:
    """The folders, and the one-byte marker that says which way up it is.

    cover/ is not scanned by anything. That is the point of it: a
    thumbnail dropped in media/ becomes a shot in the middle of your film.

    Safe to call on a folder that is already a project -- `film record`
    does, and the shape is settled when the project is made and never
    again. Marking an existing one would undo `film shape --wide` on
    somebody who only wanted somewhere to put a take.
    """
    already = (root / "media").is_dir() or (root / "film.yaml").exists()
    for sub in PROJECT_DIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    if vertical and not already:
        (root / ".vertical").write_text("1", encoding="utf-8")
    library.ensure()
    return root


def load(project: Path, quality: str) -> Film:
    yml = project / "film.yaml"
    if not yml.exists():
        raise SystemExit(
            f"No film.yaml in {project}.\n"
            f"Run `uv run film ingest` first, then ask Claude to write one."
        )
    # The opening card is derived, like a proxy: analysis/ can be deleted
    # at any time, and the title it carries can be changed in film.yaml.
    # Either would leave the film pointing at a card that is missing or
    # wrong, so it is made again here before anything reads the file.
    if cover.card_src(project) in (yml.read_text(encoding="utf-8")):
        w, h = _film_shape(project)
        cover.refresh_card(project, w, h)

    film = Film.load(yml)
    choose_moves(film.shots)

    # Film.load has already brought any over-long caption back inside its
    # shot. Say so only when it was long enough to notice -- a line you
    # meant to be read is going to be on screen for less time than you
    # asked, and that is worth one line of print, not a refusal.
    for note in film.trim_captions():
        print(f"  note: {note}")

    # For the fast tiers, silently swap in 480p proxies where they exist.
    if quality in ("peek", "draft"):
        for s in film.shots:
            if s.kind == "video":
                px = ingest_mod.proxy_for(project, s.src)
                if px:
                    s.src = px
    return film


def cmd_render(args, quality_name: str) -> None:
    project = find_project(args.project)
    q = QUALITIES[quality_name]
    if getattr(args, "supersample", None):
        q = replace(q, supersample=args.supersample)
    film = load(project, quality_name)

    out = Path(args.out) if args.out else project / "out" / f"{quality_name}.mp4"
    print(f"{film.duration:.1f}s / {len(film.shots)} shots -> {out}")

    # Record the film.yaml we are about to render, if it changed since the
    # last render. Silent when nothing changed, silent when there is no
    # git -- see history.py for how to get an old version back.
    sha = history.snapshot(
        project, f"{quality_name} - {len(film.shots)} shots, {film.duration:.1f}s")
    if sha:
        print(f"  film.yaml changed -- saved as {sha}")

    t0 = time.time()
    render(film, out, q, seed=args.seed, font=args.font)
    print(f"  done in {time.time() - t0:.1f}s")
    if quality_name == "final":
        auto_cover(project)
    guide.print_next(project)


def auto_cover(project: Path) -> None:
    """The thumbnail, made without being asked, at the moment there is a
    film to put one beside.

    Only when there is a picture to build it on -- a title on black is a
    thing somebody might want, but not a thing to hand them unasked --
    and only when the one on disk is older than the film, so a cover
    made by hand with --title is not quietly replaced by the default.
    """
    if not cover.is_stale(project):
        return
    w, h = _film_shape(project)
    if cover.choose(project, wide=w >= h).path is None:
        return
    try:
        r = build_cover(project)
    except SystemExit as e:
        print(f"  (no thumbnail: {e})")     # never worth losing a render over
        return
    print(f"  thumbnail -> {r['out']}   ({r['title']})")


def cmd_ingest(args) -> None:
    project = find_project(args.project)
    print(f"Reading {project / 'media'} ...")
    m = ingest_mod.ingest(project)
    print(f"\n{m['count']} files -> {project / 'analysis'}")
    print(f"  contact sheet: {project / 'analysis' / 'contact.jpg'}")
    print(f"  manifest:      {project / 'analysis' / 'manifest.json'}")
    guide.print_next(project)


def cmd_init(args) -> None:
    project = find_project(args.project)
    out = scaffold.write(project, force=args.force, seed=args.seed,
                         target=args.target)
    print(f"Wrote {out}")
    text = out.read_text(encoding="utf-8")
    if "NOTE: a quote_ card was placed by guesswork" in text:
        print("\nHeads up: I couldn't tell where your quote_ card belongs "
              "relative to the other shots -- check the order with "
              "`uv run film check`, or number your files (00_, 01_...) "
              "and run init again for a sure thing.")
    print("Open it -- it is meant to be read.")
    guide.print_next(project)


def cmd_caption(args) -> None:
    project = find_project(args.project)
    try:
        from . import voice, caption_fit
    except ImportError:
        raise SystemExit(
            "Captioning needs one extra package that isn't installed by "
            "default (it's about 100 MB, so it stays optional). Install it "
            "once with:\n\n  uv sync --extra voice\n\nthen run this again."
        )
    import yaml as _yaml

    if args.audio:
        audio = Path(args.audio)
        if not audio.is_absolute():
            audio = project / audio
        sources = [voice.VoiceSource(audio, audio.name, [])]
    else:
        sources = voice.voice_sources(project)

    if not sources:
        raise SystemExit(
            "No audio found anywhere. Either:\n"
            "  - put a voiceover file in media/ (voiceover.mp3, .wav...), or\n"
            "  - make sure your .mp4 clips actually have sound, or\n"
            "  - pass --audio path\\to\\file directly."
        )

    kind = "voiceover track" if not sources[0].shot_srcs else "clip(s) with talking"
    print(f"Found {len(sources)} {kind} to transcribe.\n")

    film = Film.load(project / "film.yaml") if not args.transcript_only else None
    all_placed: dict[str, list] = {}
    all_warnings: list[str] = []
    all_lines_for_transcript = []

    for src in sources:
        print(f"-- {src.label} --")
        lines = voice.transcribe(src.audio_path, model_size=args.model,
                                 language=args.lang)
        all_lines_for_transcript.append((src.label, lines))

        if args.transcript_only:
            continue

        placed, warnings = caption_fit.fit_lines_to_shots(film, src, lines)
        for sid, caps in placed.items():
            all_placed.setdefault(sid, []).extend(caps)
        all_warnings.extend(warnings)
        print()

    voice.save_transcript(project, all_lines_for_transcript)
    txt = voice.transcript_readable(project, all_lines_for_transcript)
    print(f"transcript: {txt}")

    if args.transcript_only:
        print("\n--transcript-only: film.yaml left untouched. Review the "
              "transcript above, then rerun without that flag to place "
              "captions automatically.")
        return

    if not all_placed:
        print("\nNo lines overlapped any shot's time range. If this is a "
              "voiceover track, is `audio:` set in film.yaml? If this is "
              "per-clip speech, does any shot actually use that clip?")
        return

    n = sum(len(v) for v in all_placed.values())
    print(f"\n{n} caption(s) matched to {len(all_placed)} shot(s).")
    for sid, caps in all_placed.items():
        for c in caps:
            print(f'  [{sid}] at {c.at:5.1f}s  "{c.text}"')
    if all_warnings:
        print()
        for w in all_warnings:
            print(f"  note: {w}")
        print("  (that shot may be too short for what is said over it --"
              " consider lengthening it)")

    if not args.apply:
        print("\nThis was a preview. Run again with --apply to write these "
              "into film.yaml (existing captions on affected shots are kept, "
              "new ones are added after them). You can also hand-edit any "
              "caption's text afterwards -- open film.yaml, fix the wording, "
              "save, and run peek again.")
        return

    raw = _yaml.safe_load((project / "film.yaml").read_text(encoding="utf-8"))
    for shot in raw.get("shots", []):
        caps = all_placed.get(shot.get("id", ""))
        if not caps:
            continue
        shot.setdefault("captions", [])
        for c in caps:
            # float()/str() on the way in, and safe_dump on the way out.
            # Between them, nothing that is not a plain YAML value can be
            # written into your film -- an unreadable film.yaml is a far
            # worse outcome than a caption that fails to write.
            shot["captions"].append({"text": str(c.text), "at": float(c.at),
                                     "dur": float(c.dur), "pos": str(c.pos)})
    (project / "film.yaml").write_text(
        _yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=90),
        encoding="utf-8")
    Film.load(project / "film.yaml")   # validate what we just wrote
    print(f"Written. If any line came out wrong, open film.yaml and edit "
          f"the `text:` directly.")
    guide.print_next(project)


def cmd_go(args) -> None:
    """ingest -> init -> caption -> draft, in one go."""
    project = find_project(args.project)
    name = project.name
    print(f"== {name} ==\n")

    # Check the boring things first. Discovering there is no ffmpeg two
    # minutes into a render is the sort of thing that makes people give up.
    if preflight(project, verbose=False):
        print("Before anything else:\n")
        preflight(project)
        raise SystemExit("\nFix the STOP line(s) above, then run this again.")

    print("[1/4] looking at your material")
    ingest_mod.ingest(project, quiet=True)

    # Your film.yaml is YOUR file. `go` writes one when there isn't one,
    # and otherwise leaves it alone -- so running GO again after you have
    # corrected a duration, a focus point or a caption keeps the
    # correction. --rewrite is the deliberate "start over" button, and it
    # still puts the old file next door as film.yaml.bak first.
    yml = project / "film.yaml"
    existing = yml.exists()
    if existing and not args.rewrite:
        print("[2/4] keeping the film.yaml you already have")
        added = scaffold.append_new(project, seed=args.seed)
        if added:
            print(f"      added {len(added)} new shot(s) at the end, for "
                  f"footage that was not there last time:")
            for src in added:
                print(f"        {src}")
            print("      (everything you had already tuned is untouched)")
        else:
            print("      (your edits survive. --rewrite starts over from the media)")
    else:
        if existing:
            bak = yml.with_name("film.yaml.bak")
            bak.write_text(yml.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[2/4] rewriting the edit  (old one kept as {bak.name})")
        else:
            print("[2/4] writing the edit")
        scaffold.write(project, force=True, seed=args.seed,
                       target=args.target)
        existing = False

    # Captions are APPENDED to a shot, so transcribing an already-captioned
    # film every time would stack duplicates on top of each other. Only
    # caption a film.yaml that has none yet.
    already_captioned = existing and any(
        s.captions for s in Film.load(yml).shots)

    if args.no_captions:
        print("[3/4] captions skipped (--no-captions)")
    elif already_captioned:
        print("[3/4] captions already in film.yaml -- left as they are")
        print("      (to redo them: uv run film caption --apply, or --rewrite)")
    else:
        print("[3/4] captions from your talking")
        try:
            cap_args = argparse.Namespace(
                project=args.project, audio=None, model=args.model,
                lang=args.lang, apply=True, transcript_only=False)
            cmd_caption(cap_args)
        except (SystemExit, Exception) as e:
            # Captions are the optional part. Whatever goes wrong in here --
            # a missing package, an unreadable audio track -- must not cost
            # her the film that was otherwise about to render.
            print(f"\n  skipped captions: {e}\n")

    print("\n[4/4] rendering")
    q = "final" if args.final else "draft"
    render_args = argparse.Namespace(
        project=args.project, out=None, seed=args.seed, font=args.font,
        supersample=None)
    cmd_render(render_args, q)
    # cmd_render has already printed the next step -- saying it twice
    # makes it look like two different suggestions.
    print(f"\nDone -> {project / 'out' / (q + '.mp4')}")


def cmd_check(args) -> None:
    project = find_project(args.project)
    film = load(project, "final")
    print(f"OK. {len(film.shots)} shots, {film.duration:.1f}s, "
          f"{film.width}x{film.height} @ {film.fps}fps")
    # The two things nobody typed and would otherwise have no way of
    # checking before the render: where the music came from, and what
    # the thumbnail is going to say.
    print(f"  ok    title: {film.title}")
    for line in library_lines(project):
        print(line)
    print()
    for s in film.shots:
        caps = f"  {len(s.captions)} caption(s)" if s.captions else ""
        print(f"  {s.id}  {s.duration:5.1f}s  {s.move:<12} {s.src}{caps}")
    guide.print_next(project)


def cmd_edit(args) -> None:
    project = find_project(args.project)
    if not (project / "film.yaml").exists():
        raise SystemExit("No film.yaml yet. Run `uv run film init` first.")
    editor.serve(project, port=args.port, open_browser=not args.no_browser)


def cmd_data_clip(args) -> None:
    try:
        from . import data_clip
    except ImportError as e:
        raise SystemExit(f"Missing a package for data clips: {e}\n"
                         f"This needs matplotlib, which should already be "
                         f"installed -- try `uv sync` again.")
    project = find_project(args.project) if args.project else None
    csv_path = Path(args.csv)

    if args.out:
        out = Path(args.out)
        if project and not out.is_absolute():
            out = project / out
    else:
        # Default: sit the mp4 next to the csv, same name, .mp4 instead
        # of .csv -- works whether the csv is inside the project or not.
        out = csv_path.with_suffix(".mp4")

    bg = "#f2efe9" if args.light else "#141414"
    result = data_clip.make_clip(csv_path, out, kind=args.kind,
                                 width=args.width, height=args.height,
                                 fps=args.fps, seconds=args.seconds,
                                 dark=not args.light, bg=bg)
    print(f"Wrote {result}")
    if project and result.resolve().is_relative_to(project.resolve()):
        rel = result.resolve().relative_to(project.resolve()).as_posix()
        print(f"\nAdd to film.yaml:\n\n  - src: {rel}\n"
              f"    duration: {args.seconds}\n    move: static\n")
    else:
        print(f"\nCopy this into your project's media/ folder (or point "
              f"--out there directly), then reference it in film.yaml.")


def preflight(project: Path, verbose: bool = True) -> list[str]:
    """Check the things that make a run fail two minutes in, before it does.

    Returns the list of problems. An empty list means go.
    """
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

    from . import guide as _guide
    lines.append("  ok    captions available" if _guide._voice_installed()
                 else "  --    captions off (uv sync --extra voice turns them on)")

    if verbose:
        print("\n".join(lines))
        for p in problems:
            print(f"  STOP  {p}")
    return problems


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

    w, h = _film_shape(project)
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
    return out


def _report_library() -> None:
    """Said once when a project is made: the two folders you never have
    to fill in again."""
    print(f"  music, for every film  ->  {library.music_dir()}")
    print(f"  thumbnail pictures     ->  {library.cover_dir()}")


def _record_project(arg):
    """A take should never fail for want of somewhere to put it. If you
    are standing in a project, use it; otherwise start today's."""
    try:
        return find_project(arg)
    except SystemExit:
        if arg is not None:
            raise
    from datetime import date
    root = toolkit_root() / "projects" / date.today().isoformat()
    make_project(root, vertical=True)
    print(f"Started a project for today:  {root}")
    return root


def cmd_devices(args) -> None:
    """What this machine can see, and which of it we will use."""
    from . import record as rec
    rec.require_windows()

    devices = rec.list_devices()
    if not devices:
        raise SystemExit(
            "No capture devices found.\n"
            "If the camera works in the Windows Camera app, the usual "
            "cause is another program holding it open -- Teams, Zoom, "
            "OBS, a browser tab.")

    saved = rec.load_choice()
    if args.camera or args.mic:
        cams = [d.name for d in devices if d.kind == "video"]
        mics = [d.name for d in devices if d.kind == "audio"]
        for want, have, label in ((args.camera, cams, "camera"),
                                  (args.mic, mics, "microphone")):
            if want and want not in have:
                raise SystemExit(
                    f"No {label} called {want!r} here.\n"
                    f"Available: {', '.join(have) or '(none)'}")
        video = args.camera or saved.get("video") or (cams[0] if cams else None)
        audio = args.mic or saved.get("audio") or (mics[0] if mics else None)
        rec.save_choice(video, audio)
        print("Remembered on this machine:")
        print(f"  camera      {video}")
        print(f"  microphone  {audio}")
        return

    video, audio, notes = rec.choose_devices(devices, saved)
    for kind, label in (("video", "Cameras"), ("audio", "Microphones")):
        found = [d for d in devices if d.kind == kind]
        print(f"\n{label}")
        if not found:
            print("    none found")
        for d in found:
            chosen = d.name in (video, audio)
            tail = "      <- this one is used" if chosen else ""
            print(f"  {'*' if chosen else ' '} {d.name}{tail}")

    idle = [d for d in devices if not d.usable]
    if idle:
        print("\nListed, but not available at the moment -- whatever "
              "provides these\nis not running:")
        for d in idle:
            print(f"    {d.name}")

    for n in notes:
        print(f"\n{n}")

    # An example you can paste, made from a device this computer actually
    # has. A line of the form --mic "NAME" is no use to anybody who does
    # not already know what NAME may be.
    spare = next((d.name for d in devices
                  if d.kind == "audio" and d.name != audio), None)
    if spare:
        print(f"\nTo always use a different one, for example:\n"
              f'  uv run film devices --mic "{spare}"')


def _secs(x: float) -> str:
    n = round(x)
    return f"{n} second" + ("" if n == 1 else "s")


def _ask_another(n: int) -> bool:
    """Between takes. Phrased so that the tired answer -- just pressing
    ENTER -- is the one that keeps going, because somebody who has just
    fluffed a line wants to go again, not to read a menu."""
    try:
        answer = input(f"\n  Take {n + 1}?  ENTER to go again, "
                       f"or N then ENTER if you are done:  ").strip().lower()
    except EOFError:
        return False
    return not answer.startswith(("n", "q"))


def cmd_record(args) -> None:
    """Camera + microphone -> files in media/, and nothing else."""
    from . import booth
    from . import record as rec
    from .render import ffmpeg_bin
    rec.require_windows()

    project = _record_project(args.project)
    devices = rec.list_devices()
    if not devices:
        raise SystemExit(
            "I cannot see a camera or a microphone on this computer.\n\n"
            "Almost always this means something else is using the camera.\n"
            "Close Teams, Zoom, OBS or any browser tab that might have it,\n"
            "then try again.")

    saved = rec.load_choice()
    video, audio, notes = rec.choose_devices(
        devices, saved, args.camera, args.mic)
    if not video and not audio:
        raise SystemExit("I found no camera and no microphone to record with.")
    rec.save_choice(video, audio)

    mode = rec.best_mode(rec.camera_modes(video)) if video else None
    script = booth.read_script(project, args.script)
    windowed = booth.available() and not args.no_window

    shape = f", {mode[0]}x{mode[1]}" if mode else ""
    print(f"\nCamera:      {video or '(none)'}{shape}")
    print(f"Microphone:  {audio or '(none)'}")
    for n in notes:
        print(f"             ({n})")

    takes: list[Path] = []

    def new_take():
        """One recording, started. Handed to the window as a callback so
        that the window can own the loop -- otherwise it would have to
        close and reopen between every take, and something blinking in
        and out of existence is the last thing you want in front of
        somebody who is already rattled."""
        (project / "media").mkdir(parents=True, exist_ok=True)
        out = rec.next_take_path(project / "media")
        cmd = rec.record_command(out, video, audio, mode, args.seconds,
                                 ffmpeg=ffmpeg_bin(), window=True)
        return booth.Take(cmd, out).start()

    def took(take) -> list[str]:
        """What to put on the review screen, and in the terminal behind
        it. First line is the headline, last is the running total."""
        out = take.out
        if not out.exists() or out.stat().st_size < 10_000:
            print("  That take did not save.")
            return ["That take did not save.",
                    "Something else grabbed the camera. Nothing you had "
                    "already recorded is lost -- try again.", ""]
        length, warnings = rec.verify_take(out, mode, bool(audio), take.heard)
        takes.append(out)
        print(f"  Take {len(takes)}: {_secs(length)}")
        for w in warnings:
            print(f"    Careful: {w}")
        total = sum(rec.verify_take(t, None, False)[0] for t in takes)
        return ([f"Got it. {_secs(length)}."] + warnings +
                [f"{len(takes)} take{'s' if len(takes) > 1 else ''} so far, "
                 f"{_secs(total)} in total."])

    if windowed:
        print("\nThe window is open. Everything happens in it.")
        booth.session(script=script, script_path=project / "script.txt",
                      wpm=args.wpm, title=project.name,
                      start=new_take, finish=took, seconds=args.seconds)
    else:
        print("\nLook at the camera, not at the screen.")
        while True:
            (project / "media").mkdir(parents=True, exist_ok=True)
            out = rec.next_take_path(project / "media")
            cmd = rec.record_command(out, video, audio, mode, args.seconds,
                                     ffmpeg=ffmpeg_bin(), window=False)
            print(f"\n  Take {len(takes) + 1}")
            for n in (3, 2, 1):
                print(f"\r     {n}...   ", end="", flush=True)
                time.sleep(1)
            if args.seconds:
                print(f"\r     recording for {args.seconds:g} seconds.      ")
            else:
                print("\r     recording -- press ENTER when you have "
                      "finished talking.  ")
            rec.run_recording(cmd, args.seconds)

            if not out.exists() or out.stat().st_size < 10_000:
                print("\n  That take did not save. The usual reason is "
                      "another\n  program grabbing the camera. Nothing "
                      "else is lost.")
            else:
                length, warnings = rec.verify_take(out, mode, bool(audio))
                takes.append(out)
                print(f"\n  Got it -- {_secs(length)}.")
                for w in warnings:
                    print(f"  Careful: {w}")
            if args.seconds or not _ask_another(len(takes)):
                break

    if not takes:
        raise SystemExit("\nNothing was recorded. Nothing has changed.")

    total = sum(rec.verify_take(t, None, False)[0] for t in takes)
    print(f"\n  {len(takes)} take{'s' if len(takes) > 1 else ''}, "
          f"{_secs(total)}, saved in {project.name}\\media\\")
    print(f"  In the edit they play at {rec.REC_SPEED}x so they do not drag,")
    print("  and the silences get trimmed. Both are numbers you can change.")
    guide.print_next(project)


def _film_shape(project: Path) -> tuple[int, int]:
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


def build_cover(project: Path, title: str | None = None,
                image: str | None = None, wide: bool = False,
                pos: str = "bottom", font: str | None = None) -> dict:
    """Make the thumbnail.

    Shared by `film cover` and by `film final`, which builds one on its
    own -- so there is exactly one set of rules about which picture and
    which words, whichever way you came in.
    """
    width, height = cover.WIDE if wide else _film_shape(project)
    back = cover.choose(project, image, wide=width >= height)
    words = cover.title_from(back, title, project)
    frame = cover.compose(back.path, words, width, height, pos, font)
    out = cover.out_path(project)
    return {"out": out, "size": cover.save(frame, out), "title": words,
            "width": width, "height": height, "backdrop": back}


def cmd_cover(args) -> None:
    """The miniature: a still to upload beside the film."""
    project = find_project(args.project)
    cover.cover_dir(project).mkdir(exist_ok=True)
    library.ensure()

    r = build_cover(project, args.title, args.image, args.wide, args.pos,
                    args.font)
    back = r["backdrop"]

    if back.path is None:
        print("No picture anywhere yet, so this is just the title on black.")
        print("Drop a wide one and a tall one in")
        print(f"  {library.cover_dir()}")
        print("and every film you make gets a cover of its own shape.")
        print()
    print(f"Cover:  {r['out']}")
    print(f"        {r['width']}x{r['height']}, {r['size'] / 1000:.0f} KB")
    print(f"        title: \"{r['title']}\"")
    if back.path is not None:
        print(f"        from:  {back.path}"
              + ("   (your library)" if back.shared else ""))


def cmd_library(args) -> None:
    """Open the shelf, and say what is on it."""
    base = library.ensure()
    if base is None:
        raise SystemExit("The library is switched off: FFILM_LIBRARY is set "
                         "to nothing.\nUnset it, or point it at a folder.")
    print(f"Your library:  {base}")
    print()
    track = library.music()
    print("  music/   " + (track.name if track
                           else "(empty -- put one file here)"))
    pictures = library.backdrops()
    for pic in pictures:
        shape = {True: "wide", False: "tall", None: "not a picture?"}[
            library.is_wide(pic)]
        print(f"  cover/   {pic.name}   ({shape})")
    if not pictures:
        print("  cover/   (empty -- put a wide picture and a tall one here)")
    print()
    print("Everything in here is used by EVERY film. A film with its own")
    print("music/ or cover/ folder uses that instead.")
    if not args.no_open:
        guide.open_folder(base)


def cmd_pack(args) -> None:
    """A zip you can carry to another computer."""
    from . import pack as pk

    root = toolkit_root()
    projects = list(args.projects or [])
    if args.all:
        projects = sorted(p.name for p in (root / "projects").iterdir()
                          if p.is_dir()) if (root / "projects").is_dir() else []

    name = pk.default_name(projects)
    # Beside the folder, never inside it -- a zip written into the tree
    # it is zipping is a zip that tries to contain itself.
    out = Path(args.out) if args.out else root.parent / name

    files = pk.contents(root, projects)
    raw = sum(p.stat().st_size for p, _ in files)
    print(f"Packing {len(files)} files ({raw / 1e6:.1f} MB) ...")
    size = pk.build(root, out, projects)

    print(f"\n  {out}")
    print(f"  {size / 1e6:.1f} MB")
    if projects:
        print(f"  toolkit + {', '.join(projects)} (originals, not renders)")
    else:
        print("  the toolkit only -- no films. `--project NAME` adds one.")
    print("\nOn the other computer: unzip it, run SETUP.bat once, then "
          "FILM.bat.")


def cmd_doctor(args) -> None:
    project = find_project(args.project)
    print(f"Checking {project.name} ...\n")
    if not preflight(project):
        print("\nNothing in the way. Run:  uv run film")


def cmd_shape(args) -> None:
    """Switch a finished film between vertical and widescreen.

    Only the resolution changes. Nothing is re-cropped by hand, because
    nothing needs to be: the camera window is chosen in the SOURCE image
    and sampled to whatever shape the frame is, so a horizontal photo in a
    1080x1920 frame is cropped to fill, around its focus point. Which is
    why this is one line in film.yaml and not a feature.
    """
    import re as _re
    project = find_project(args.project)
    yml = project / "film.yaml"
    if not yml.exists():
        raise SystemExit(f"No film.yaml in {project} yet.")

    w, h = (1080, 1920) if args.vertical else (1920, 1080)
    line = f"resolution: [{w}, {h}]"
    if args.vertical:
        line += "   # vertical, for YouTube Shorts"

    # Rewritten as text, not as parsed YAML, so your comments survive.
    raw = yml.read_text(encoding="utf-8")
    out, n = _re.subn(r"(?m)^resolution:.*$", line, raw, count=1)
    if n == 0:
        out, n = _re.subn(r"(?m)^(fps:.*)$", r"\1\n" + line, raw, count=1)
    if n == 0:
        out = line + "\n" + raw
    yml.write_text(out, encoding="utf-8")

    marker = project / ".vertical"
    if args.vertical:
        marker.write_text("1", encoding="utf-8")
    elif marker.exists():
        marker.unlink()

    shape = "1080x1920 vertical (Shorts/Reels/TikTok)" if args.vertical \
        else "1920x1080 widescreen"
    print(f"{yml.name} is now {shape}.")
    print("Everything is re-framed around each shot's focus point -- "
          "nothing is letterboxed.")
    if args.vertical:
        print("If a wide clip loses too much that way -- a face filmed "
              "close up\nis the usual one -- add `fill: blur` to film.yaml "
              "and it keeps the\npicture whole on a blurred copy of itself "
              "instead.")
    guide.print_next(project)


def cmd_drop(args) -> None:
    """Files were dropped onto FILM.bat. Make a film out of them.

    The shortest path there is: select the clips in Explorer, drag them
    onto FILM.bat, watch the film. No name to think of, no folders to
    find, nothing typed.
    """
    import shutil as _shutil
    from datetime import date

    media_ext, music_ext = kinds.MEDIA, kinds.AUDIO

    given = [Path(f) for f in args.files]
    files = []
    for g in given:
        files.extend(sorted(p for p in g.rglob("*") if p.is_file())
                     if g.is_dir() else [g])
    keep = [p for p in files if p.suffix.lower() in media_ext | music_ext]
    if not keep:
        raise SystemExit("None of those are photos, clips or music.")

    # Named for the day, because you are not going to think of a name
    # while standing on a beach.
    base = toolkit_root() / "projects" / date.today().isoformat()
    root, n = base, 2
    while root.exists():
        root, n = Path(f"{base}_{n}"), n + 1
    make_project(root, vertical=not args.wide)

    photos = clips = tracks = 0
    for p in keep:
        if p.suffix.lower() in music_ext:
            _shutil.copy2(p, root / "music" / p.name)
            tracks += 1
        else:
            _shutil.copy2(p, root / "media" / p.name)
            if p.suffix.lower() in kinds.VIDEO:
                clips += 1
            else:
                photos += 1

    (toolkit_root() / ".lastfilm").write_text(root.name, encoding="utf-8")
    shape = "widescreen" if args.wide else "vertical"
    print(f"Copied into {root.name}  [{shape}]:  {photos} photo(s), "
          f"{clips} clip(s), {tracks} music track(s).")
    print("Your originals are untouched.\n")

    guide.walk(root)


def cmd_new(args) -> None:
    root = make_project(toolkit_root() / "projects" / args.name,
                        vertical=args.vertical)
    shape = "1080x1920 vertical (YouTube Shorts)" if args.vertical else "1920x1080"
    print(f"Created {root}   [{shape}]")
    print(f"  photos + clips  ->  {root / 'media'}")
    _report_library()
    guide.print_next(root)


def main() -> None:
    # The Windows console defaults to a codepage that cannot print half of
    # Europe. Without this, a caption reading "Kolobrzeg" comes back as
    # "Ko?obrzeg" on screen -- the film itself is fine, but you cannot
    # proofread what you are being shown.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(prog="film", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=False)

    p = sub.add_parser("next", help="what do I do next? (same as bare `film`)")
    p.add_argument("--project", "-p", default=None)

    def common(p):
        p.add_argument("--project", "-p", default=None)
        p.add_argument("--out", "-o", default=None)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--font", default=None, help="path to a .ttf for captions")
        p.add_argument("--supersample", type=int, default=None,
                       help="render Nx then shrink. Slower, marginally cleaner.")
        return p

    for name in ("peek", "draft", "final"):
        common(sub.add_parser(name, help=f"render at {name} quality"))

    p = sub.add_parser("ingest", help="analyse the media folder")
    p.add_argument("--project", "-p", default=None)

    p = sub.add_parser("init", help="write a first film.yaml from the manifest")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--target", type=float, default=None,
                   help="aim for this many seconds. Shortens and drops "
                        "PICTURES only -- never your speech.")

    p = sub.add_parser("caption", help="transcribe a voiceover into captions")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--audio", default=None, help="path to the voiceover, if not in media/")
    p.add_argument("--model", default="small",
                   choices=["tiny", "base", "small", "medium", "large-v3"])
    p.add_argument("--lang", default=None, help="e.g. en, pl -- auto-detected if omitted")
    p.add_argument("--apply", action="store_true", help="write captions into film.yaml")
    p.add_argument("--transcript-only", action="store_true",
                   help="just transcribe, don't touch film.yaml")

    p = sub.add_parser("check", help="validate film.yaml")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--font", default=None)

    p = sub.add_parser("edit", help="open the editing bench in your browser")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--port", type=int, default=8731)
    p.add_argument("--no-browser", action="store_true")

    p = sub.add_parser("data-clip", help="turn a CSV into an animated clip")
    p.add_argument("csv")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--out", "-o", default=None)
    p.add_argument("--kind", default="line", choices=["line", "bar_race", "counter"])
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--seconds", type=float, default=6.0)
    p.add_argument("--light", action="store_true", help="light text/axes instead of dark")

    p = sub.add_parser("go", help="ingest + init + caption + render, one command")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--font", default=None)
    p.add_argument("--model", default="small")
    p.add_argument("--lang", default=None)
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--target", type=float, default=None,
                   help="aim for this many seconds (pictures only)")
    p.add_argument("--rewrite", action="store_true",
                   help="throw away the existing film.yaml and write a fresh "
                        "one from the media (the old one is kept as .bak)")
    p.add_argument("--final", action="store_true", help="render final, not draft")

    p = sub.add_parser("doctor", help="check everything is in place")
    p.add_argument("--project", "-p", default=None)

    p = sub.add_parser("shape", help="switch between vertical and widescreen")
    p.add_argument("--project", "-p", default=None)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--vertical", action="store_true",
                   help="1080x1920, cropped to fill around each focus point")
    g.add_argument("--wide", action="store_true", help="1920x1080")

    p = sub.add_parser("drop", help="make a film from files dropped on FILM.bat")
    p.add_argument("files", nargs="+")
    p.add_argument("--wide", action="store_true",
                   help="widescreen instead of vertical")

    p = sub.add_parser("pack", help="make a zip to carry to another computer")
    p.add_argument("--project", "-p", dest="projects", action="append",
                   default=None,
                   help="also pack this film's originals (repeatable)")
    p.add_argument("--all", action="store_true",
                   help="pack every project's originals too")
    p.add_argument("--out", default=None, help="where to write the zip")

    p = sub.add_parser("library",
                       help="the music and cover pictures every film uses")
    p.add_argument("--no-open", action="store_true",
                   help="just list it, do not open the folder")

    p = sub.add_parser("cover", help="build the thumbnail")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--title", default=None,
                   help="the words on it (default: what the film is called)")
    p.add_argument("--image", default=None,
                   help="use this picture instead of the one in cover/")
    p.add_argument("--wide", action="store_true",
                   help="1280x720 instead of the film's own shape")
    p.add_argument("--pos", default="bottom",
                   choices=["bottom", "top", "center", "lower_third"])
    p.add_argument("--font", default=None)

    p = sub.add_parser("record", help="record from your camera and microphone")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--seconds", "-t", type=float, default=None,
                   help="stop after this many seconds instead of on ENTER")
    p.add_argument("--camera", default=None,
                   help="camera name (see `film devices`)")
    p.add_argument("--mic", default=None, help="microphone name")
    p.add_argument("--script", default=None,
                   help="text file to scroll while you talk "
                        "(default: script.txt in the project)")
    p.add_argument("--wpm", type=int, default=105,
                   help="how fast the script scrolls, in words per minute")
    p.add_argument("--no-window", action="store_true",
                   help="no preview window, just the terminal")

    p = sub.add_parser("devices", help="list cameras and microphones")
    p.add_argument("--camera", default=None, help="always use this camera")
    p.add_argument("--mic", default=None, help="always use this microphone")

    p = sub.add_parser("new", help="create a project folder")
    p.add_argument("name")
    p.add_argument("--vertical", action="store_true",
                   help="1080x1920 for YouTube Shorts / Reels / TikTok")

    args = ap.parse_args()
    try:
        # No subcommand at all: the walk-through. This is the one command
        # worth remembering -- it tells you all the others.
        if args.cmd is None:
            guide.walk()
        elif args.cmd == "next":
            try:
                guide.walk(find_project(args.project))
            except SystemExit:
                guide.walk()
        elif args.cmd in ("peek", "draft", "final"):
            cmd_render(args, args.cmd)
        elif args.cmd == "ingest":
            cmd_ingest(args)
        elif args.cmd == "init":
            cmd_init(args)
        elif args.cmd == "caption":
            cmd_caption(args)
        elif args.cmd == "check":
            cmd_check(args)
        elif args.cmd == "edit":
            cmd_edit(args)
        elif args.cmd == "data-clip":
            cmd_data_clip(args)
        elif args.cmd == "go":
            cmd_go(args)
        elif args.cmd == "doctor":
            cmd_doctor(args)
        elif args.cmd == "shape":
            cmd_shape(args)
        elif args.cmd == "drop":
            cmd_drop(args)
        elif args.cmd == "new":
            cmd_new(args)
        elif args.cmd == "cover":
            cmd_cover(args)
        elif args.cmd == "library":
            cmd_library(args)
        elif args.cmd == "pack":
            cmd_pack(args)
        elif args.cmd == "record":
            cmd_record(args)
        elif args.cmd == "devices":
            cmd_devices(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise                        # our own messages, already in plain words
    except Exception as exc:
        # Anything that reaches here is a bug, not something she did. She
        # gets one sentence and a file to send me; the eighty lines of
        # Python go in the file, where they are useful and not frightening.
        import traceback
        log = toolkit_root() / "last_error.txt"
        try:
            log.write_text(
                f"{' '.join(sys.argv)}\n\n{traceback.format_exc()}",
                encoding="utf-8")
            where = f"\nThe details are in:  {log}\nSend me that file."
        except OSError:
            where = ""
        print(f"\nSomething went wrong inside the toolkit -- this is a bug, "
              f"not anything you did.\n\n  {type(exc).__name__}: "
              f"{str(exc)[:200]}\n"
              f"\nYour film.yaml and your media are untouched.{where}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
