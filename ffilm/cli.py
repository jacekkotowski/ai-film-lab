"""
cli.py  --  the commands you type.

    uv run film                     "what do I do next?" -- it walks you
                                    through, one step at a time. Start here
                                    if you do not remember the rest.

    uv run film go                  the whole film in one go: look, edit,
                                    captions, render a draft
    uv run film record              say it to the camera, with a script scrolling

    uv run film ingest              look at the media, build the contact sheet
    uv run film peek                ~seconds   is the ORDER right?
    uv run film draft               ~a minute  does the MOTION feel right?
    uv run film final               minutes    ship it

    uv run film init                write a first film.yaml automatically
    uv run film edit                open the editing bench in your browser
    uv run film new <name>          start a new project folder
    uv run film check               validate film.yaml without rendering
    uv run film undo                back to a version you already watched
    uv run film library             the music + cover pictures every film uses
    uv run film models              fetch the model files once (also automatic)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
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
from .checks import (bokeh_notes, film_shape, framing_notes, library_lines,
                     caption_share_line, music_notes, narration_notes,
                     preflight_report, unused_media)
from .moves import choose_moves
from .paths import toolkit_root
from .render import QUALITIES, render
from .spec import Film
from .spec import title_of as spec_title_of

def find_project(arg: str | None) -> Path:
    """Find the project folder without requiring `cd` into AI-Film first.

    If you did not pass -p, and the folder you are standing in already
    looks like a project (has media/ or film.yaml), we use THAT folder --
    this is what makes `uv run film ingest` work with no arguments when
    you are sitting inside your own project directory in RStudio.

    Failing that, the film you were last on. That is what `uv run film`
    has always used, and this did not: it fell back to a hardcoded
    `projects/film_001` that has never existed on anybody's disk, so
    `uv run film peek` with no -p failed by naming an imaginary folder.
    """
    cwd = Path.cwd()
    if arg is None and ((cwd / "media").is_dir() or (cwd / "film.yaml").exists()):
        return cwd.resolve()

    if arg is None:
        last = guide.last_project()
        if last is not None:
            return last.resolve()
        started = guide.known_projects()
        if started:
            return started[0].resolve()
        raise SystemExit(
            "No film to work on yet.\n"
            "Start one:      uv run film new my_movie\n"
            "or be walked through it:   uv run film")

    p = Path(arg)
    candidates = [p]
    if not p.is_absolute():
        candidates.append(toolkit_root() / p)
        candidates.append(toolkit_root() / "projects" / p.name)

    for c in candidates:
        if (c / "media").is_dir() or (c / "film.yaml").exists():
            found = c.resolve()
            guide.remember(found)
            return found

    started = [q.name for q in guide.known_projects()]
    known = ("\n\nFilms you have started:\n"
             + "\n".join(f"  - {s}" for s in started[:12])) if started else ""
    raise SystemExit(
        f"No project found for {arg!r}.\n"
        f"Looked in:\n" + "\n".join(f"  - {c}" for c in candidates) + known +
        f"\n\nIf this is a brand new project, create it first:\n"
        f"  uv run film new {_arg(p.name or 'my_movie')}\n"
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


def keep_a_copy(project: Path) -> Path | None:
    """Put the current film.yaml aside before something overwrites it.

    `go --rewrite` did this and `init --force` did not, so the same act --
    throw away the edit and write a fresh one from the media -- was
    recoverable by one command and not by the other. Nothing about which
    command you reached for should decide whether your work survives.

    A render also commits film.yaml (see history.py), so `film undo` can
    reach further back than this. This is the copy you can see.
    """
    yml = project / "film.yaml"
    if not yml.exists():
        return None
    bak = yml.with_name("film.yaml.bak")
    try:
        bak.write_text(yml.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        return None
    return bak


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
        w, h = film_shape(project)
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
    for line in narration_notes(film):
        print(line)

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
        ship(project, film, out, open_page=not getattr(args, "no_open", False))
    elif not getattr(args, "no_open", False):
        # peek and draft exist to be WATCHED -- "is the ORDER right?",
        # "does the MOTION feel right?" -- and the loop they belong to is
        # the whole system. Going round it should not include finding the
        # file yourself every time.
        guide.play(out)
    guide.print_next(project)


UPLOAD_PAGE = "https://www.youtube.com/upload"


def ship(project: Path, film, out: Path, open_page: bool = True) -> None:
    """Everything between "it is rendered" and "it is uploaded".

    Which is: the words, checked against what YouTube will accept, and
    then the two windows you would have opened anyway. Not an uploader --
    see the note in cover.py for why not.
    """
    has_audio = True
    try:
        from .ffmpeg import ffprobe_bin
        r = subprocess.run(
            [ffprobe_bin(), "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True)
        has_audio = bool(r.stdout.strip())
    except (OSError, ValueError):
        pass

    problems = cover.shorts_problems(film.width, film.height,
                                     film.duration, has_audio)
    title = getattr(film, "title", None) or spec_title_of(project)
    notes = cover.upload_path(project)
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(cover.upload_notes(title, film, problems),
                     encoding="utf-8")
    print(f"  what to paste -> {notes}")
    for p in problems:
        print(f"    Careful: {p}")

    if open_page:
        guide.open_folder(out.parent)
        try:
            webbrowser.open(UPLOAD_PAGE)
        except Exception:
            print(f"    (open {UPLOAD_PAGE} yourself)")


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
    w, h = film_shape(project)
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
    # --force throws away an edit. Keep it where she can find it, the same
    # way `go --rewrite` always has.
    bak = keep_a_copy(project) if args.force else None
    out = scaffold.write(project, force=args.force, seed=args.seed,
                         target=args.target)
    print(f"Wrote {out}")
    if bak is not None:
        print(f"  the edit you had is kept as {bak.name}")
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
    # Loaded before the sources are chosen, because a film whose slides
    # carry `voice:` changes what its narration IS: not one track under
    # the whole film, but a source whose pieces are quoted by particular
    # shots. See voice.slides_using.
    film = Film.load(project / "film.yaml") if not args.transcript_only else None

    if args.audio:
        audio = Path(args.audio)
        if not audio.is_absolute():
            audio = project / audio
        sources = [voice.VoiceSource(audio, audio.name,
                                     voice.slides_using(film, audio))]
    else:
        sources = voice.voice_sources(project, film)

    if not sources:
        raise SystemExit(
            "No audio found anywhere. Either:\n"
            "  - put a voiceover file in media/ (voiceover.mp3, .wav...), or\n"
            "  - make sure your .mp4 clips actually have sound, or\n"
            "  - pass --audio path\\to\\file directly."
        )

    if any(s.voice for s in (film.shots if film else [])):
        kind = "narration, cut across the slides"
    elif sources[0].shot_srcs:
        kind = "clip(s) with talking"
    else:
        kind = "voiceover track"
    print(f"Found {len(sources)} {kind} to transcribe.\n")

    all_placed: dict[str, list] = {}
    all_warnings: list[str] = []
    all_lines_for_transcript = []

    cuts: list = []
    for src in sources:
        print(f"-- {src.label} --")
        # The words you wrote, if you wrote any. They decide where a
        # caption ends; the transcript only decides when.
        from . import booth
        script = booth.read_script(project, None)
        lines = voice.transcribe(src.audio_path, model_size=args.model,
                                 language=args.lang, script=script)
        all_lines_for_transcript.append((src.label, lines))

        if args.transcript_only:
            continue

        # One paragraph of the script is one slide. `init` cut this
        # narration at its longest pauses, which is a guess and says so;
        # the script is where the person actually said where the subject
        # changes. Applied to the film in memory first, so the preview
        # below shows the film being asked for and not the one being
        # replaced.
        paragraphs = voice.script_paragraphs(script or "")
        if paragraphs and any(s.voice for s in film.shots):
            windows = voice.paragraph_windows(
                lines, paragraphs, breath=scaffold.BREATH)
            cuts = scaffold.slide_cuts(film, paragraphs, windows)
            if cuts:
                film = scaffold.apply_cuts(film, cuts)
                missed = sum(1 for w in windows if w is None)
                print(f"  {len(cuts)} slide(s) re-cut by paragraph"
                      + (f", {missed} paragraph(s) not found in what was "
                         f"said" if missed else ""))
                for c, s in zip(cuts, [s for s in film.shots if s.voice]):
                    print(f"  [{s.id}] {c.tin:6.2f}-{c.tout:6.2f}  "
                          f"{Path(c.src).name}")

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

    # Said once, and said again on a later shot: usually an outtake that
    # stayed in. Named here; which reading to keep is yours to decide.
    with_new = replace(film, shots=[
        replace(s, captions=list(s.captions) + all_placed.get(s.id, []))
        for s in film.shots])
    again = caption_fit.re_reads(with_new)
    if again:
        listed = "  ".join(f"{sid} ({secs:.1f}s)" for sid, secs in again)
        print(f"\n  re-reads, said again on a later shot: {listed}")
        print(f"  {sum(secs for _, secs in again):.0f}s of the film. Delete "
              f"the earlier shot if the later reading is the keeper.")

    if not args.apply:
        if cuts:
            print("\nThe slide windows above are a preview too -- --apply "
                  "writes them into film.yaml alongside the captions.")
        print("\nThis was a preview. Run again with --apply to write these "
              "into film.yaml (existing captions on affected shots are kept, "
              "new ones are added after them). You can also hand-edit any "
              "caption's text afterwards -- open film.yaml, fix the wording, "
              "save, and run peek again.")
        return

    # Spliced in as TEXT. It used to be safe_load + safe_dump, which is
    # valid YAML and deleted every comment in the file -- including the
    # whole header `film init` writes explaining what the numbers mean.
    # `film go` captions on its own, so that header was gone before
    # anybody had read the file once.
    yml = project / "film.yaml"
    before = yml.read_text(encoding="utf-8")
    # The slides move first, then the captions are placed on them. The
    # other order would fit every line to a window that is about to
    # change.
    text = scaffold.recut_slides(before, cuts) if cuts else before
    yml.write_text(scaffold.add_captions(text, all_placed), encoding="utf-8")
    try:
        Film.load(yml)                 # validate what we just wrote
    except SystemExit as e:
        yml.write_text(before, encoding="utf-8")
        raise SystemExit(
            f"Adding the captions would have broken film.yaml, so nothing "
            f"was changed:\n\n  {e}\n\nThe transcript is still saved -- see "
            f"above -- so nothing was lost.")
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
    # Once, not twice: this used to run the whole check to decide whether
    # to print it, and then run it all again to print it.
    lines, problems = preflight_report(project)
    if problems:
        print("Before anything else:\n")
        print("\n".join(lines))
        for p in problems:
            print(f"  STOP  {p}")
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
        bak = keep_a_copy(project)
        if bak is not None:
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
        supersample=None, no_open=getattr(args, "no_open", False))
    cmd_render(render_args, q)
    # cmd_render has already printed the next step -- saying it twice
    # makes it look like two different suggestions.
    print(f"\nDone -> {project / 'out' / (q + '.mp4')}")


def _arg(text: str) -> str:
    """A value as it must be TYPED. Quoted when it has a space in it.

    Every command this prints is printed to be retyped, and a film called
    `Zima nad morzem` printed bare reads as a project called Zima and
    three stray arguments -- which fails for a reason nobody would guess
    from looking at it.
    """
    return f'"{text}"' if " " in text else text


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
    for line in music_notes(film):
        print(line)
    for line in narration_notes(film):
        print(line)
    share = caption_share_line(film)
    if share:
        print(share)
    print()
    for s in film.shots:
        caps = f"  {len(s.captions)} caption(s)" if s.captions else ""
        print(f"  {s.id}  {s.duration:5.1f}s  {s.move:<12} {s.src}{caps}")

    missing = unused_media(project, film)
    if missing:
        print(f"\n  !! {len(missing)} file(s) in media\\ are in NO shot, so "
              f"they will not\n     appear in the film:")
        for m in missing[:20]:
            print(f"       {m}")
        if len(missing) > 20:
            print(f"       ... and {len(missing) - 20} more")
        print("\n     Two reasons this happens: footage that arrived after "
              "the edit was")
        print("     written, and pictures left out to hit a --target "
              "length. Either way,")
        print("     to put them back at the end, keeping everything you "
              "have tuned:")
        # Quoted. A film called `Zima nad morzem` printed bare reads as a
        # project called Zima plus three stray arguments -- the same
        # mistake guide.Step.pretty exists to avoid.
        print(f"       uv run film go -p {_arg(project.name)}")

    for note in framing_notes(film):
        print(f"  {note}" if note.startswith("[") else note)
    for note in bokeh_notes(film):
        print(f"  {note}")

    guide.print_next(project)


def cmd_edit(args) -> None:
    project = find_project(args.project)
    if not (project / "film.yaml").exists():
        raise SystemExit("No film.yaml yet. Run `uv run film init` first.")
    editor.serve(project, port=args.port, open_browser=not args.no_browser)


def preflight(project: Path, verbose: bool = True) -> list[str]:
    """Check the things that make a run fail two minutes in, before it does.

    Returns the list of problems. An empty list means go.
    """
    lines, problems = preflight_report(project)
    if verbose:
        print("\n".join(lines))
        for p in problems:
            print(f"  STOP  {p}")
    return problems


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
    from .ffmpeg import ffmpeg_bin
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
    if args.voice:
        # No camera at all -- not "whatever choose_devices would have
        # picked, discarded". Asking camera_modes() below would open the
        # device just to throw the answer away, and the whole point of
        # --voice is a narration read over PHOTOGRAPHS, not a clip.
        _, audio, notes = rec.choose_devices(devices, saved, None, args.mic)
        video = None
        rec.save_choice(saved.get("video"), audio)
    else:
        video, audio, notes = rec.choose_devices(
            devices, saved, args.camera, args.mic)
        rec.save_choice(video, audio)
    if not video and not audio:
        raise SystemExit("I found no camera and no microphone to record with.")

    mode = rec.best_mode(rec.camera_modes(video)) if video else None
    script = booth.read_script(project, args.script)
    windowed = booth.available() and not args.no_window

    if args.voice:
        print("\nVoice only -- no camera. Reads over your photographs, "
              "not to a lens.")
    else:
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
        out = rec.next_take_path(project / "media", audio_only=args.voice)
        cmd = rec.record_command(out, video, audio, mode, args.seconds,
                                 ffmpeg=ffmpeg_bin(), window=True)
        return booth.Take(cmd, out).start()

    def took(take) -> list[str]:
        """What to put on the review screen, and in the terminal behind
        it. First line is the headline, last is the running total."""
        out = take.out
        if not out.exists() or out.stat().st_size < 10_000:
            print("  That take did not save.")
            # ffmpeg says why. It always said why -- these lines were
            # collected and then thrown away, and a guess was printed
            # over the top of them. "Something else grabbed the camera"
            # sent me looking for a program holding the webcam for an
            # hour, while the real reason was sitting unread in this
            # list.
            for line in take.errors[-3:]:
                print(f"    {line}")
            return ["That take did not save."] + (
                [take.errors[-1]] if take.errors else
                ["Something else may have grabbed the camera."]) + [
                "Nothing you had already recorded is lost -- try again.", ""]
        length, warnings = rec.verify_take(out, mode, bool(audio), take.heard)
        takes.append(out)
        print(f"  Take {len(takes)}: {_secs(length)}")
        for w in warnings:
            print(f"    Careful: {w}")
        total = sum(rec.verify_take(t, None, False)[0] for t in takes)
        return ([f"Got it. {_secs(length)}."] + warnings +
                [f"{len(takes)} take{'s' if len(takes) > 1 else ''} so far, "
                 f"{_secs(total)} in total."])

    def drop_last() -> None:
        """Throw away the take just made, because it was fluffed.

        Every take kept becomes a shot, so going again after a fumbled
        line used to put the fumble in the film beside the good version.
        This is the one thing in the toolkit that removes something from
        media/, and it does it only when somebody presses the button
        that says so, about a take made seconds earlier.

        Moved, not deleted: `media/_discarded/`, the same shape as
        `media/_unreadable/`, so a mis-click costs nothing and nothing
        here ever destroys a recording outright.
        """
        if not takes:
            return
        gone = takes.pop()
        try:
            kept = ingest_mod.quarantine(gone, project / "media",
                                         where=kinds.DISCARDED_DIRNAME)
            print(f"  dropped {gone.name} -> {kept.parent.name}\\")
        except OSError as e:
            print(f"  could not put {gone.name} aside: {e}")

    if windowed:
        print("\nThe window is open. Everything happens in it.")
        booth.session(script=script, script_path=project / "script.txt",
                      wpm=args.wpm, title=project.name,
                      start=new_take, finish=took, seconds=args.seconds,
                      discard=drop_last)
    else:
        print("\nJust talk." if args.voice else
              "\nLook at the camera, not at the screen.")
        while True:
            (project / "media").mkdir(parents=True, exist_ok=True)
            out = rec.next_take_path(project / "media", audio_only=args.voice)
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
    if args.voice:
        print("  `film init` reads it as the narration and stretches your "
              "photographs to cover it.")
    else:
        print(f"  In the edit they play at {rec.REC_SPEED}x so they do not "
              f"drag,")
        print("  and the silences get trimmed. Both are numbers you can "
              "change.")
    guide.print_next(project)


def build_cover(project: Path, title: str | None = None,
                image: str | None = None, wide: bool = False,
                pos: str = "bottom", font: str | None = None) -> dict:
    """Make the thumbnail.

    Shared by `film cover` and by `film final`, which builds one on its
    own -- so there is exactly one set of rules about which picture and
    which words, whichever way you came in.
    """
    width, height = cover.WIDE if wide else film_shape(project)
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


def cmd_models(args) -> None:
    """Fetch any model file that is not here yet, and say what is."""
    from . import models
    print(f"Models:  {models.models_dir()}")
    print()
    if not args.check:
        for m in models.CATALOGUE:
            models.ensure(m)
    for line in models.status_lines():
        print(line)


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


def cmd_undo(args) -> None:
    """Go back to a film.yaml you have already watched.

    Every render saves the film.yaml it is about to render, if it changed
    -- see history.py. That has been true from the start and there was no
    way to use it that did not involve typing

        git show a6511a2:projects/my_movie/film.yaml > projects/...

    which is not a thing to ask of somebody who is tired and has just
    made their film worse.
    """
    project = find_project(args.project)
    saved = history.versions(project)
    if not saved:
        raise SystemExit(
            f"No saved versions of {project.name}\\film.yaml yet.\n"
            f"Every render saves one, if the file changed since the last "
            f"one -- so there will be some after you have been round the "
            f"loop once or twice.\n"
            f"(This needs git. If `git --version` says nothing, that is why.)")

    if args.list:
        print(f"Saved versions of {project.name}\\film.yaml, newest first:\n")
        for i, (sha, what) in enumerate(saved, 1):
            print(f"  [{i}]  {sha}  {what}")
        print(f"\nTo go back to one:  uv run film undo -p "
              f"{_arg(project.name)} --to {saved[-1][0]}")
        return

    if args.to:
        pick = next((v for v in saved if v[0].startswith(args.to)), None)
        if pick is None:
            raise SystemExit(
                f"No saved version starting {args.to!r}.\n"
                f"  uv run film undo -p {_arg(project.name)} --list   shows them.")
    else:
        # No argument: the one before the version on disk now. That is
        # what "undo" means, and it is the only thing anybody types.
        pick = saved[1] if len(saved) > 1 else saved[0]

    text = history.restore(project, pick[0])
    if text is None:
        raise SystemExit(f"Could not read {pick[0]} back out of git.")

    yml = project / "film.yaml"
    now = yml.read_text(encoding="utf-8") if yml.exists() else ""
    if text == now:
        print(f"film.yaml is already exactly version {pick[0]}. "
              f"Nothing to undo.")
        print(f"  uv run film undo -p {_arg(project.name)} --list   "
              f"shows the rest.")
        return

    # The version being replaced is kept where the guide can find it, so
    # undoing an undo is one command and not an act of faith.
    keep = yml.with_name("film.yaml.bak")
    if now:
        keep.write_text(now, encoding="utf-8")
    yml.write_text(text, encoding="utf-8")
    try:
        film = Film.load(yml)
    except SystemExit as e:
        yml.write_text(now, encoding="utf-8")
        raise SystemExit(f"That version will not load, so nothing was "
                         f"changed:\n\n  {e}")

    print(f"Back to {pick[0]}  --  {pick[1]}")
    print(f"  {len(film.shots)} shots, {film.duration:.1f}s")
    if now:
        print(f"  what you had is kept as {keep.name}, in case you want it "
              f"back")
    guide.print_next(project)


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

    guide.remember(root)
    shape = "widescreen" if args.wide else "vertical"
    print(f"Copied into {root.name}  [{shape}]:  {photos} photo(s), "
          f"{clips} clip(s), {tracks} music track(s).")
    print("Your originals are untouched.\n")

    guide.walk(root)


def cmd_new(args) -> None:
    # `film new` with nothing after it is a real thing to type, and the
    # name it picks is the same one the walk-through offers.
    name = guide.tidy_name(args.name or "") or guide.default_name(
        taken=[p.name for p in guide.known_projects()])
    vertical = not args.wide
    root = make_project(toolkit_root() / "projects" / name,
                        vertical=vertical)
    guide.remember(root)
    shape = "1080x1920 vertical (YouTube Shorts)" if vertical else "1920x1080"
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
        p = sub.add_parser(name, help=f"render at {name} quality")
        common(p)
        p.add_argument("--no-open", action="store_true",
                       help="do not open the out folder and the YouTube "
                            "upload page afterwards" if name == "final"
                       else "do not open the film when it is rendered")

    p = sub.add_parser("ingest", help="analyse the media folder")
    p.add_argument("--project", "-p", default=None)

    p = sub.add_parser("init", help="write a first film.yaml from the manifest")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--target", type=float, default=None,
                   help="aim for this many seconds. Shortens and drops "
                        "PICTURES only -- never your speech.")

    p = sub.add_parser("caption", help="put what you said in your clips on screen (or a voiceover)")
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

    p = sub.add_parser("edit", help="open the editing bench in your browser")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--port", type=int, default=8731)
    p.add_argument("--no-browser", action="store_true")

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
    # cmd_go already looked for this with getattr and never found it,
    # because nothing declared it -- so `go` always opened a player,
    # which is right in front of a person and wrong from a script.
    p.add_argument("--no-open", action="store_true",
                   help="do not open the film when it is rendered")

    p = sub.add_parser("doctor", help="check everything is in place")
    p.add_argument("--project", "-p", default=None)

    p = sub.add_parser("undo", help="go back to a film.yaml you already watched")
    p.add_argument("--project", "-p", default=None)
    p.add_argument("--list", action="store_true",
                   help="show the saved versions instead of going back")
    p.add_argument("--to", default=None,
                   help="a particular one, by the code `--list` shows")

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

    p = sub.add_parser("models",
                       help="fetch the model files (bokeh, voice cleaning) "
                            "into models/")
    p.add_argument("--check", action="store_true",
                   help="just say which are there, fetch nothing")

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
    p.add_argument("--voice", action="store_true",
                   help="microphone only -- no camera. For a narration "
                        "read over photographs; writes voiceover_*.wav")
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
    p.add_argument("name", nargs="?", default=None,
                   help="left out: named for the time of day and the date, "
                        "e.g. Morning_2026-09-05")
    # Vertical unless you say otherwise. Every film made here so far has
    # been one, the walk-through has always defaulted to it, and only
    # this command disagreed -- so `film new` and pressing ENTER made
    # differently shaped films out of the same answer.
    p.add_argument("--vertical", action="store_true",
                   help="1080x1920 for YouTube Shorts / Reels / TikTok "
                        "(the default)")
    p.add_argument("--wide", "--widescreen", action="store_true",
                   dest="wide", help="1920x1080 instead")

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
        elif args.cmd == "go":
            cmd_go(args)
        elif args.cmd == "doctor":
            cmd_doctor(args)
        elif args.cmd == "undo":
            cmd_undo(args)
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
        elif args.cmd == "models":
            cmd_models(args)
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
