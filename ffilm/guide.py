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

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
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
    ask_length: bool = False                     # offer --target before running

    @property
    def pretty(self) -> str:
        # Quoted, because this line is printed to be RETYPED -- that is
        # the whole reason it is printed. A film called `Morning 2026`
        # came out as `-p Morning 2026`, which reads as a project called
        # Morning and a stray argument, and fails for a reason nobody
        # would guess from looking at it. It still ran when you pressed
        # ENTER, because that path passes a list and never goes near a
        # shell -- so this was wrong only in the copy somebody typed.
        parts = self.shell or (["uv", "run", "film"] + self.args)
        return " ".join(f'"{x}"' if " " in x else x for x in parts)


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
    # media/_unreadable/ is where ingest puts what it could not read. It
    # is inside media/, so rglob finds it, and counting it meant a
    # project holding nothing but one broken take looked like a project
    # with footage in it.
    times = [_mtime(f) for f in folder.rglob("*")
             if f.suffix.lower() in exts and not kinds.is_aside(f, folder)]
    return max(times) if times else 0.0


def _manifest_counts(manifest: Path) -> tuple[int, int]:
    """How many files ingest could use, and how many it could not.

    Returns (-1, 0) when there is no manifest yet, so "not ingested" and
    "ingested and found nothing" stay different answers.
    """
    try:
        d = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return -1, 0
    return int(d.get("count", 0) or 0), len(d.get("unreadable") or [])


# When the day stops being one thing and starts being the next. Ordinary
# waking hours, not astronomical ones -- this names a film, it does not
# settle an argument about when evening begins.
TIME_OF_DAY = ((5, "Morning"), (12, "Afternoon"), (18, "Evening"),
               (22, "Night"))


def part_of_day(when: datetime) -> str:
    """Morning / Afternoon / Evening / Night, for an hour of the clock."""
    name = "Night"                      # before 5am, and after 10pm
    for hour, label in TIME_OF_DAY:
        if when.hour >= hour:
            name = label
    return name


def default_name(when: datetime | None = None,
                 taken: Iterable[str] = ()) -> str:
    """What to call a film when you did not want to name it.

    `Morning_2026-09-05`. The date in ISO order so a folder listing sorts
    itself, and the part of the day in front because that is how you will
    actually remember which one it was.

    Never returns a name that is already in `taken` -- two films in one
    afternoon is an ordinary thing to do, and silently opening the first
    one again instead of making a second is not.
    """
    when = when or datetime.now()
    base = f"{part_of_day(when)}_{when:%Y-%m-%d}"
    taken = set(taken)
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


# What Windows will not have in a folder name. Everything else is
# yours, including spaces.
ILLEGAL = set('<>:"/\\|?*')


def tidy_name(name: str) -> str:
    """A name somebody typed, made safe to be a folder -- and no further.

    Spaces are KEPT. The project name is the film's title, and a title is
    written with spaces: `Zima nad morzem` should stay exactly that, not
    become `Zima Nad Morzem`, which is what turning it into underscores
    and title-casing it back produces.

    Spaces were briefly banned here because the guide prints commands to
    be retyped and `-p Morning 2026-09-15` reads as a project called
    Morning plus a stray argument. That is now fixed where it belonged,
    in Step.pretty, which quotes it.
    """
    kept = "".join(" " if (c in ILLEGAL or ord(c) < 32) else c for c in name)
    return " ".join(kept.split()).strip(" .")


def projects_dir() -> Path:
    from .paths import toolkit_root
    return toolkit_root() / "projects"


def known_projects() -> list[Path]:
    d = projects_dir()
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_dir()),
                  key=_mtime, reverse=True)


def lastfilm_path() -> Path:
    return projects_dir().parent / ".lastfilm"


def remember(project: Path) -> None:
    """The film you are on, so the next `uv run film` comes back to it.

    Called from every place that CHANGES which film you are on, which
    used to be only two of the four: making one and dropping files on
    FILM.bat wrote it, but switching with [F] and naming one with -p did
    not. So you could switch to a second film, work in it, close the
    window, and be handed the first one again next time.
    """
    try:
        if project.parent.resolve() == projects_dir().resolve():
            lastfilm_path().write_text(project.name, encoding="utf-8")
    except OSError:
        pass


def last_project() -> Path | None:
    """The film named in .lastfilm, if it is still there."""
    last = lastfilm_path()
    if not last.exists():
        return None
    try:
        name = last.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    cand = projects_dir() / name
    return cand if name and cand.is_dir() else None


def current_project() -> Path | None:
    """The project we should be talking about, with no -p given.

    The folder you are standing in wins -- that is what makes this work
    when you have `cd`-ed into a project from RStudio. Otherwise the one
    made last, otherwise the most recently touched.
    """
    cwd = Path.cwd()
    if (cwd / "media").is_dir() or (cwd / "film.yaml").exists():
        return cwd.resolve()

    cand = last_project()
    if cand is not None:
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


def _get_material(project: Path, unreadable: int = 0) -> list[Step]:
    """There is nothing to make a film out of yet -- go and get some.

    Two ways to arrive here, not one: an empty project, and a project
    whose files ingest could not read. The second used to fall through
    to "write a first edit", and `init` cannot write a film with no
    shots in it -- so the guide offered the one step that was certain to
    fail, and offered it again every time it did.
    """
    p = ["-p", project.name]
    media = project / "media"
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
    # Say it plainly when the folder is not empty but might as well be.
    # "Drag your photos in" over a folder that already has a file in it
    # reads as though nothing happened at all.
    note = ""
    if unreadable:
        note = (f"The {unreadable} file(s) already in media\\ could not be "
                f"read, so\n"
                f"there is nothing to build a film from yet -- they are in\n"
                f"media\\{kinds.UNREADABLE_DIRNAME}\\ and nothing was "
                f"deleted. A take that did\n"
                f"not save is the usual reason.\n\n")
    # One window, not two. The music and the thumbnail picture come
    # off the shared shelf, which is filled in once and never again --
    # so the only folder anybody has to look at is this film's own
    # pictures. `film library` is where the other two live.
    return [Step(
        "Drag your photos and clips into the folder that just opened",
        why=note + "media\\  ->  your photos, your clips, your AI intro\n"
            "\n"
            + _shelf_note() + "\n"
            "If you care about the order, put a number in front of the\n"
            "filename:\n"
            "\n"
            "    00_ 01_ 02_               they play in that order\n"
            "    open_close_hello.png      opens AND closes the film\n"
            "    quote_stay_curious.png    a held card, filename is the text",
        folders=[media])] + record_step


def wants_voiceover(entries: list[dict], film_has_audio: bool) -> bool:
    """Photographs with nobody talking over them, and no narration set
    yet -- exactly the film that `record --voice` finishes. Pure, off
    entries the shape ingest's manifest already writes them in.

    A talking clip already IS a narration of sorts, so offering to
    record a second one over the top would compete with it rather than
    help -- same reasoning as voice.voice_sources rule 1 outranking a
    clip's own speech.
    """
    if film_has_audio:
        return False
    from . import scaffold
    has_still = any(e.get("kind") == "still" for e in entries)
    has_talking = any(e.get("kind") == "video" and scaffold.is_talking(e)
                      for e in entries)
    return has_still and not has_talking


def _manifest_media(manifest: Path) -> list[dict]:
    try:
        d = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return d.get("media") or []


def next_steps(project: Path) -> list[Step]:
    """What to do next, best first. The rest are the sensible alternatives."""
    name = project.name
    p = ["-p", name]

    manifest = project / "analysis" / "manifest.json"
    usable, unreadable = _manifest_counts(manifest)

    media = project / "media"
    newest_media = _newest(media, MEDIA_EXT)
    if not newest_media:
        return _get_material(project, unreadable)

    if _mtime(manifest) < newest_media:
        return [
            Step("Build the whole film in one go", ["go"] + p,
                 why="Looks at your material, writes the edit, adds captions "
                     "from your talking, and renders a draft you can watch.",
                 ask_length=True),
            Step("...or take it one step at a time, starting here",
                 ["ingest"] + p,
                 why="Finds the faces and the interesting part of each picture."),
        ]

    # Ingested, and there was nothing in it. Never offer `init` here:
    # it refuses with "No usable media found", which is correct of it
    # and useless as a next step.
    if usable == 0:
        return _get_material(project, unreadable)

    yml = project / "film.yaml"
    if not yml.exists():
        return [Step("Write a first edit", ["init"] + p,
                     why="Turns what it saw into a film.yaml -- order, "
                         "durations, camera moves. All of it changeable.")]

    edited = _mtime(yml)

    # A voiceover recorded (or dropped in) after the last edit has not
    # been folded into it: `init` is what stretches the photographs to
    # cover it and starts it after the opening card (2026-09-17 plan,
    # items 2 and 3). Without this check, the manifest is not older than
    # the media -- ingest never reads audio -- so the guide would offer
    # `peek` and quietly play the new narration under the old pictures.
    narration = _newest(project / "media", AUDIO_EXT)
    if narration and narration > edited:
        # `go --rewrite`, not `init --force`. Both write the slides; only
        # `go` goes on to transcribe them, so `init` alone left the words
        # on the soundtrack and never on the screen -- which is exactly
        # what Jacek's test of test_story found on 2026-09-17.
        return [Step("Fold your narration into the edit",
                     ["go", "--rewrite"] + p,
                     why="A voiceover arrived after the last edit. This "
                         "gives each photograph its own piece of it, puts "
                         "the words on screen, and renders a draft. What "
                         "you had is kept as film.yaml.bak.")]

    out = project / "out"
    # A render answers every question a rougher one would have: `go`
    # makes a draft, and a draft settles the order too; `final` settles
    # both. Being told to render a worse version of what you have just
    # watched is exactly the nonsense this guide exists to avoid.
    final_ok = _mtime(out / "final.mp4") >= edited
    peek_ok = final_ok or _mtime(out / "peek.mp4") >= edited
    draft_ok = final_ok or _mtime(out / "draft.mp4") >= edited

    if not peek_ok and not draft_ok:
        steps = [
            Step("Watch it -- is the ORDER right?", ["peek"] + p,
                 why="Seconds to render. Small and choppy on purpose."),
            Step("...or open the bench and click the shots first",
                 ["edit"] + p,
                 why="Click a photo to say what the camera should look at."),
        ]
        from .spec import headers
        if (sys.platform == "win32"
                and wants_voiceover(_manifest_media(manifest),
                                    bool(headers(yml).get("audio")))):
            steps.append(Step(
                "...or say the words over these pictures",
                ["record", "--voice"] + p,
                why="Same window as talking to the camera, minus the "
                    "camera. `init` picks it up as the narration and "
                    "stretches the photographs to cover it."))
        return steps

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

    # Only once there is somewhere to go back TO. Every render saves the
    # film.yaml it rendered, and until now the only way to use that was a
    # git command with a path in it -- which is not a thing to ask of
    # somebody who has just made their film worse and knows it.
    from . import history
    if len(history.versions(project, limit=2)) > 1:
        steps.append(Step("...or put it back the way it was",
                          ["undo"] + p,
                          why="Back to the last film.yaml you watched. Every "
                              "render saves one. What you have now is kept "
                              "as film.yaml.bak, so this is undoable too."))

    if final_ok:
        steps.insert(0, Step("Done. final.mp4 is up to date -- upload it",
                             folders=[out], done=True,
                             why="Change anything in film.yaml and the loop "
                                 "starts again on its own."))
    return steps


def _voice_installed() -> bool:
    from .checks import voice_installed
    return voice_installed()


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


def play(path: Path) -> None:
    """Open a finished render in whatever plays video on this machine.

    The same call as open_folder -- os.startfile opens a folder in
    Explorer and a file in its default application -- but the name says
    which one is meant at the call site.
    """
    open_folder(path)


def _run(args: list[str]) -> int:
    """Run one film command in a child process, exactly as printed."""
    print()
    sys.stdout.flush()          # or our lines land after the child's
    r = subprocess.run([sys.executable, "-m", "ffilm.cli", *args])
    return r.returncode


def _ask_length(args: list[str]) -> list[str]:
    """Offer a length before building, once, where the decision is.

    `--target` has existed and worked from the start, and the guide never
    mentioned it -- so shortening a film meant knowing that a flag exists.

    Never shortens speech, whatever is typed here -- see
    scaffold.fit_to_target. This only ever touches the pictures.
    """
    if "--target" in args:
        return args
    print(f"\n  How long should it be? Pictures are shortened to fit; "
          f"nothing you\n  said is ever cut.")
    a = _ask("\n  ENTER to keep the whole film, or a number of seconds:  ")
    if a.lower().startswith("q"):
        return args
    return _length_args(args, a)


def _length_args(args: list[str], answer: str) -> list[str]:
    """What an answer to the length question adds to the command.

    ENTER used to mean "about 60 seconds", so a take recorded in full came
    out with its pictures squeezed to a minute unless you knew to type 0.
    Asked on 2026-09-15: nothing is shortened unless a number is typed --
    and a typo counts as nothing, because it must not shorten the film
    either.
    """
    try:
        want = float(answer.strip().replace(",", "."))
    except ValueError:
        return args
    return args if want <= 0 else args + ["--target", f"{want:g}"]


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
    # Offered, not demanded. Naming a thing before it exists is the
    # hardest question this asks anybody, and pressing ENTER used to
    # answer it with "Nothing created." -- which reads as a refusal when
    # it was only a blank.
    suggested = default_name(taken=[p.name for p in known_projects()])
    name = _ask(f"A name for it, or ENTER for {suggested}:  ")
    if name.lower() == "q":
        print("\nNothing created.")
        return None
    typed, name = name.strip(), tidy_name(name) or suggested
    # The name becomes the title, so a character quietly disappearing
    # from it is a title quietly wrong. Windows will not have < > : " /
    # \ | ? * in a folder name and there is nothing to be done about
    # that -- but being told beats finding out on the thumbnail.
    if typed and name != typed:
        lost = "".join(sorted({c for c in typed if c in ILLEGAL}))
        if lost:
            print(f"\n  Windows will not have {' '.join(lost)} in a folder "
                  f"name, so this film is called\n  \"{name}\".")
            print(f"  For the full version on screen, put it in film.yaml:"
                  f"\n      title: \"{typed}\"")
    shape = _ask("ENTER for vertical (Shorts), or W for widescreen:  ")
    args = ["new", name] + (["--wide"] if shape.lower() == "w" else [])
    print(f"\n  uv run film {' '.join(args)}")
    if _run(args) != 0:
        return None
    made = projects_dir() / name
    if made.is_dir():
        remember(made)
        return made
    return None


def other_choices(n_steps: int) -> str:
    """How the alternatives are offered at the prompt. One alternative is
    "2", not "2-2"."""
    if n_steps <= 1:
        return ""
    if n_steps == 2:
        return ", 2 for another"
    return f", 2-{n_steps} for another"


def walk(project: Path | None = None) -> None:
    """Ask, act, ask again. The whole app for someone in a hurry."""
    interactive = sys.stdin.isatty()

    if project is None:
        project = current_project()
    else:
        remember(project)
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
        choices = first + other_choices(len(steps))
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
                remember(project)
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
        run_args = _ask_length(chosen.args) if chosen.ask_length else chosen.args
        if _run(run_args) != 0:
            # A take that did not save is the ordinary case here, not a
            # broken installation -- you fluffed it, something grabbed the
            # camera, you closed the window. Ending the whole walk-through
            # at "press any key" means going back to the start for what is
            # nearly always just: go again.
            print("\nThat stopped early -- the reason is above.")
            if not interactive:
                return
            if _ask("\n  ENTER to try that again, or Q to stop:  ").startswith("q"):
                return
            last_title = None
            continue

    print("\nThat is a lot of steps. Run `uv run film` again to carry on.")
