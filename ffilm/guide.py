"""
guide.py  --  "what do I do next?"

    uv run film

That one command, with nothing after it, is the whole interface if you
want it to be. It looks at your project, works out which step is missing,
tells you the command in full, and offers to run it for you. Say yes
enough times and you have a film.

It always PRINTS the command before running it. That is deliberate --
after a few films you will know them, and then you can stop asking and
type them yourself. The guide is training wheels that show you the road.

Every other command ends by calling `print_next()` from here, so wherever
you are, the next step is on screen without you having to come back and
ask for it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import kinds

MEDIA_EXT = kinds.MEDIA
AUDIO_EXT = kinds.AUDIO


@dataclass
class Step:
    title: str                                   # imperative, one line
    args: list[str] = field(default_factory=list)   # empty = you do this, not a command
    why: str = ""
    folders: list[Path] = field(default_factory=list)   # opened for you
    done: bool = False                           # nothing left to do -- stop here
    shell: list[str] = field(default_factory=list)   # not a `film` command

    @property
    def pretty(self) -> str:
        if self.shell:
            return " ".join(self.shell)
        return "uv run film " + " ".join(self.args)


# --------------------------------------------------------------------------
# Reading the state of a project off the disk
# --------------------------------------------------------------------------


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _newest(folder: Path, exts: set[str]) -> float:
    if not folder.is_dir():
        return 0.0
    times = [_mtime(f) for f in folder.rglob("*") if f.suffix.lower() in exts]
    return max(times) if times else 0.0


def projects_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "projects"


def known_projects() -> list[Path]:
    d = projects_dir()
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_dir()),
                  key=_mtime, reverse=True)


def current_project() -> Path | None:
    """The project we should be talking about, with no -p given.

    The folder you are standing in wins -- that is what makes this work
    when you have `cd`-ed into a project from RStudio. Otherwise the one
    made last, otherwise the most recently touched.
    """
    cwd = Path.cwd()
    if (cwd / "media").is_dir() or (cwd / "film.yaml").exists():
        return cwd.resolve()

    last = projects_dir().parent / ".lastfilm"
    if last.exists():
        name = last.read_text(encoding="utf-8").strip()
        cand = projects_dir() / name
        if cand.is_dir():
            return cand
    found = known_projects()
    return found[0] if found else None


def _shelf_note() -> str:
    """What to say about the shared library on the card that asks for
    files: that it is looking after the music and the thumbnail already,
    or that it is short of one of them and how to fix that."""
    from . import library
    missing = [what for what, got in
               (("music", library.music()),
                ("thumbnail picture", library.backdrops())) if not got]
    if not missing:
        return ("Music and the thumbnail picture come from your library,\n"
                "so there is nothing else to set up.\n")
    return (f"Your library has no {' and no '.join(missing)} yet.\n"
            f"`uv run film library` opens it -- fill it in once and every\n"
            f"film gets both. Or skip it: the film still works.\n")


def next_steps(project: Path) -> list[Step]:
    """What to do next, best first. The rest are the sensible alternatives."""
    name = project.name
    p = ["-p", name]

    media = project / "media"
    newest_media = _newest(media, MEDIA_EXT)
    if not newest_media:
        # An empty project is the one moment where "say it to the camera"
        # is a real alternative to "go and find some files", so it is the
        # one place worth offering. Windows only, because that is where
        # `film record` works -- see record.py.
        record_step = ([Step(
            "...or say it to the camera right now", ["record"] + p,
            why="A window opens. Paste in what you want to say -- it\n"
                "scrolls while you talk -- or leave it empty and just\n"
                "speak. You can see yourself and watch the sound level.\n"
                "SPACE ends a take, and it offers you another.")]
            if sys.platform == "win32" else [])
        # One window, not two. The music and the thumbnail picture come
        # off the shared shelf, which is filled in once and never again --
        # so the only folder anybody has to look at is this film's own
        # pictures. `film library` is where the other two live.
        return [Step(
            "Drag your photos and clips into the folder that just opened",
            why="media\\  ->  your photos, your clips, your AI intro\n"
                "\n"
                + _shelf_note() + "\n"
                "If you care about the order, put a number in front of the\n"
                "filename:\n"
                "\n"
                "    00_ 01_ 02_               they play in that order\n"
                "    open_close_hello.png      opens AND closes the film\n"
                "    quote_stay_curious.png    a held card, filename is the text",
            folders=[media])] + record_step

    manifest = project / "analysis" / "manifest.json"
    if _mtime(manifest) < newest_media:
        return [
            Step("Build the whole film in one go", ["go"] + p,
                 why="Looks at your material, writes the edit, adds captions "
                     "from your talking, and renders a draft you can watch."),
            Step("...or take it one step at a time, starting here",
                 ["ingest"] + p,
                 why="Finds the faces and the interesting part of each picture."),
        ]

    yml = project / "film.yaml"
    if not yml.exists():
        return [Step("Write a first edit", ["init"] + p,
                     why="Turns what it saw into a film.yaml -- order, "
                         "durations, camera moves. All of it changeable.")]

    edited = _mtime(yml)
    out = project / "out"
    # A render answers every question a rougher one would have: `go`
    # makes a draft, and a draft settles the order too; `final` settles
    # both. Being told to render a worse version of what you have just
    # watched is exactly the nonsense this guide exists to avoid.
    final_ok = _mtime(out / "final.mp4") >= edited
    peek_ok = final_ok or _mtime(out / "peek.mp4") >= edited
    draft_ok = final_ok or _mtime(out / "draft.mp4") >= edited

    if not peek_ok and not draft_ok:
        return [
            Step("Watch it -- is the ORDER right?", ["peek"] + p,
                 why="Seconds to render. Small and choppy on purpose."),
            Step("...or open the bench and click the shots first",
                 ["edit"] + p,
                 why="Click a photo to say what the camera should look at."),
        ]

    if not draft_ok:
        return [
            Step("Watch it properly -- does the MOTION feel right?",
                 ["draft"] + p,
                 why="Under a minute. This is the one you judge the camera on."),
            Step("...or fix a shot first", ["edit"] + p,
                 why="Focus points and durations, by clicking and dragging."),
        ]

    steps = [Step("Ship it", ["final"] + p,
                  why="Full quality, a few minutes. This is the upload.")]

    # Only once there is a film to put one beside, and only while there
    # is not one already -- `film final` builds it, so most of the time
    # this step is already done by the time anybody could take it.
    from . import cover
    if cover.is_stale(project):
        steps.append(Step("...or make the thumbnail now", ["cover"] + p,
                          why="The film's name over a picture from your "
                              "library. `film final` does it for you "
                              "anyway -- this is for seeing it early."))

    if not any(s.captions for s in _shots_of(yml)):
        if _voice_installed():
            steps.append(Step("...or put your talking on screen first",
                              ["caption", "--apply"] + p,
                              why="Transcribes the speech in your clips and "
                                  "places it as captions, timed to the word."))
        else:
            # The reason captions "didn't happen" is almost always this:
            # the speech model is a 100MB optional extra, and nothing ever
            # offered to fetch it. Offer it.
            steps.append(Step("...or install captions (one time, ~100 MB)",
                              shell=["uv", "sync", "--extra", "voice"],
                              why="Captions come from your own talking, "
                                  "transcribed on this machine. The model is "
                                  "not bundled, so it has to be fetched once. "
                                  "After this, captions happen on their own."))

    if film_is_wide(yml):
        steps.append(Step("...or make it vertical, for Shorts",
                          ["shape", "--vertical"] + p,
                          why="Re-framed around each shot's focus point. "
                              "Nothing is letterboxed."))
    steps.append(Step("...or change something", ["edit"] + p,
                      why="Then peek again. Round and round -- that is the job."))
    if final_ok:
        steps.insert(0, Step("Done. final.mp4 is up to date -- upload it",
                             folders=[out], done=True,
                             why="Change anything in film.yaml and the loop "
                                 "starts again on its own."))
    return steps


def _voice_installed() -> bool:
    """Is the optional speech model package there?"""
    from importlib.util import find_spec
    try:
        return find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


def film_is_wide(yml: Path) -> bool:
    from .spec import Film
    try:
        f = Film.load(yml)
        return f.width >= f.height
    except SystemExit:
        return False


def _shots_of(yml: Path):
    """Shots, or an empty list if the file is mid-edit and unparseable."""
    from .spec import Film
    try:
        return Film.load(yml).shots
    except SystemExit:
        return []


# --------------------------------------------------------------------------
# The one-line footer every command prints
# --------------------------------------------------------------------------


def print_next(project: Path) -> None:
    """One line at the end of every command: where you are, what is next."""
    try:
        steps = next_steps(project)
    except Exception:
        return
    if not steps:
        return
    s = steps[0]
    print()
    if s.args:
        print(f"Next:  {s.pretty}")
        print(f"       {s.title.lower()}")
    else:
        print(f"Next:  {s.title}")
    print("       (or just `uv run film` and it will walk you through it)")


# --------------------------------------------------------------------------
# The interactive walk-through
# --------------------------------------------------------------------------


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def open_folder(folder: Path) -> None:
    try:
        os.startfile(str(folder))            # Windows. Silent everywhere else.
    except Exception:
        pass


def _run(args: list[str]) -> int:
    """Run one film command in a child process, exactly as printed."""
    print()
    sys.stdout.flush()          # or our lines land after the child's
    r = subprocess.run([sys.executable, "-m", "ffilm.cli", *args])
    return r.returncode


def _claude_ready() -> bool:
    return shutil.which("claude") is not None


def _ask_claude(project: Path) -> None:
    """Hand the terminal to Claude, then come back to the walk-through.

    Started in the toolkit folder, because that is where CLAUDE.md lives --
    the working agreement that keeps it editing your film.yaml instead of
    rewriting the machine that renders it.
    """
    print()
    print("  Say what is wrong in your own words -- any language.")
    print(f"  Tell it which film: \"in {project.name}, shot 2 is too long\".")
    print("  Type /exit when you are done and you will come back here.\n")
    sys.stdout.flush()
    try:
        subprocess.run(["claude"], cwd=str(projects_dir().parent))
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  could not start claude: {e}")


def _pick_project(current: Path) -> Path | None:
    """Choose among the films already started."""
    found = known_projects()
    if not found:
        return None
    print("\n  Which film?\n")
    for i, p in enumerate(found, 1):
        here = "  <- the one you are on" if p.resolve() == current.resolve() else ""
        done = "final.mp4" if (p / "out" / "final.mp4").exists() else "in progress"
        print(f"   [{i}] {p.name:<24} {done}{here}")
    a = _ask("\n  Number, or ENTER to stay where you are:  ")
    if a.isdigit() and 1 <= int(a) <= len(found):
        return found[int(a) - 1]
    return None


def _make_project() -> Path | None:
    print("\nStarting a new film.\n")
    name = _ask("A name for it (no spaces, e.g. morning01):  ")
    if not name or name == "q":
        print("\nNothing created.")
        return None
    shape = _ask("ENTER for vertical (Shorts), or W for widescreen:  ")
    args = ["new", name] + ([] if shape.lower() == "w" else ["--vertical"])
    print(f"\n  uv run film {' '.join(args)}")
    if _run(args) != 0:
        return None
    made = projects_dir() / name
    (projects_dir().parent / ".lastfilm").write_text(name, encoding="utf-8")
    return made if made.is_dir() else None


def walk(project: Path | None = None) -> None:
    """Ask, act, ask again. The whole app for someone in a hurry."""
    interactive = sys.stdin.isatty()

    if project is None:
        project = current_project()
    if project is None:
        if not interactive:
            print("No project yet. Start one with:  uv run film new my_movie")
            return
        project = _make_project()
        if project is None:
            return

    last_title = None
    for _ in range(40):                       # a loop, not a recursion. Safe.
        steps = next_steps(project)
        s = steps[0]

        # Same step as last time round -- she pressed ENTER before the files
        # had finished copying, or dragged them somewhere else. Say so in one
        # line rather than repeating the whole card at her, and do not throw
        # another pair of Explorer windows on top of the ones already open.
        repeat = s.title == last_title and bool(s.folders)
        last_title = s.title

        if repeat:
            # Short, and no Explorer window on top of the one already
            # open -- but the alternatives still have to be SEEN, not
            # just still work if you happen to remember the number.
            # This used to drop them, which made "say it to the camera"
            # look like an option that had quietly gone away the moment
            # you pressed ENTER a second time.
            print("\n  Still nothing in media\\. Drop the files in first.")
            for i, alt in enumerate(steps[1:], 2):
                print(f"\n  [{i}] {alt.title}")
                if alt.args or alt.shell:
                    print(f"      {alt.pretty}")
        else:
            print()
            print("=" * 62)
            print(f"  {project.name}")
            print("=" * 62)
            print(f"\n  {s.title}")
            for line in s.why.splitlines():
                print(f"  {line}")
            if s.args or s.shell:
                print(f"\n      {s.pretty}")
            for i, alt in enumerate(steps[1:], 2):
                print(f"\n  [{i}] {alt.title}")
                if alt.args or alt.shell:
                    print(f"      {alt.pretty}")
            for f in s.folders:
                open_folder(f)

        if not interactive:
            return

        # Standing options. These are on offer at every step, including a
        # finished film -- which is the whole point: you are never stuck
        # inside one project.
        others = len(known_projects()) > 1
        print("\n  [N] Start a NEW film")
        if others:
            print("  [F] Switch to another film you have already started")
        claude = _claude_ready()
        if claude:
            print("  [C] Something feels wrong and you would rather just say so")

        if s.done:
            first = "ENTER to stop"
        elif s.folders:
            first = "ENTER when the files are in"
        else:
            first = "ENTER to run it"
        choices = first + (
            f", 2-{len(steps)} for another" if len(steps) > 1 else "")
        choices += ", N for a new film"
        if others:
            choices += ", F to switch"
        if claude:
            choices += ", C for Claude"
        answer = _ask(f"\n{choices}, or Q to stop:  ").lower()
        if answer == "q" or (answer == "" and s.done):
            print("\nStopped. Nothing is lost -- run `uv run film` any time.")
            return
        if answer == "n":
            made = _make_project()
            if made is not None:
                project, last_title = made, None
            continue
        if answer == "f" and others:
            picked = _pick_project(project)
            if picked is not None:
                project, last_title = picked, None
            continue
        if answer == "c" and claude:
            _ask_claude(project)
            last_title = None            # it may have changed everything
            continue
        chosen = s
        if answer.isdigit() and 2 <= int(answer) <= len(steps):
            chosen = steps[int(answer) - 1]
        if chosen is s and s.folders:
            continue                     # go and look again
        if chosen.shell:
            print()
            sys.stdout.flush()
            subprocess.run(chosen.shell, cwd=str(projects_dir().parent))
            last_title = None
            continue
        if not chosen.args:
            for f in chosen.folders:
                open_folder(f)
            continue
        if _run(chosen.args) != 0:
            print("\nThat stopped early -- the reason is above. Fix it and "
                  "run `uv run film` again.")
            return

    print("\nThat is a lot of steps. Run `uv run film` again to carry on.")
