"""
spec.py  --  what a film IS.

Read this file first. Everything else in the toolkit exists to turn the
objects defined here into pixels. If you understand this file, you own
the system.

A film.yaml looks like this:

    fps: 24
    resolution: [1920, 1080]
    audio: media/music.mp3
    fill: crop                 # crop | blur -- see Film.fill below
    look:
      grain: 0.3
      vignette: 0.25

    shots:
      - src: media/harbour.jpg
        duration: 6.0
        move: push_in
        focus: [0.42, 0.38]        # normalised x,y of the thing that matters
        ease: sine_in_out
        captions:
          - text: "Kolobrzeg, November"
            at: 1.0
            dur: 2.5

      - src: media/walk.mp4
        in: "00:02:14.5"
        out: "00:02:19.0"
        move: punch_in

Coordinate conventions, used everywhere:
  cx, cy   centre of the crop window, 0..1 across the SOURCE image
           (0,0 = top-left, 1,1 = bottom-right, 0.5,0.5 = dead centre)
  scale    1.0 = the window fills the frame. 1.3 = zoomed in 30%.
  roll     degrees. Positive = clockwise. Keep it under 1.0 or it looks drunk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import kinds

# --------------------------------------------------------------------------
# Small pieces
# --------------------------------------------------------------------------


@dataclass
class Window:
    """A crop window over the source image. The camera, essentially."""

    cx: float = 0.5
    cy: float = 0.5
    scale: float = 1.0
    roll: float = 0.0

    @staticmethod
    def parse(d: Any) -> "Window":
        if d is None:
            return Window()
        if isinstance(d, Window):
            return d
        return Window(
            cx=float(d.get("cx", 0.5)),
            cy=float(d.get("cy", 0.5)),
            scale=float(d.get("scale", 1.0)),
            roll=float(d.get("roll", 0.0)),
        )

    def lerp(self, other: "Window", t: float) -> "Window":
        """Blend between two windows. t=0 gives self, t=1 gives other."""
        return Window(
            cx=self.cx + (other.cx - self.cx) * t,
            cy=self.cy + (other.cy - self.cy) * t,
            scale=self.scale + (other.scale - self.scale) * t,
            roll=self.roll + (other.roll - self.roll) * t,
        )


@dataclass
class Caption:
    """A line of text over the picture. Fades in and out automatically."""

    text: str
    at: float = 0.0            # seconds from the start of THIS shot
    dur: float = 3.0
    pos: str = "bottom"        # bottom | top | center | lower_third
    size: float = 1.0          # multiplier on the default size
    fade: float = 0.4          # seconds of fade at each end

    @staticmethod
    def parse(d: Any) -> "Caption":
        if isinstance(d, str):
            return Caption(text=d)
        return Caption(
            text=str(d["text"]),
            at=float(d.get("at", 0.0)),
            dur=float(d.get("dur", 3.0)),
            pos=str(d.get("pos", "bottom")),
            size=float(d.get("size", 1.0)),
            fade=float(d.get("fade", 0.4)),
        )


@dataclass
class Look:
    """Grade and texture. Applied identically to every shot, which is what
    makes a sequence feel like one film rather than a folder of clips."""

    grain: float = 0.0         # 0..1. 0.3 is tasteful, 1.0 is Super 8.
    vignette: float = 0.0      # 0..1
    saturation: float = 1.0
    contrast: float = 1.0
    lift: float = 0.0          # raises the blacks. 0.02-0.05 = filmic.
    scratches: float = 0.0     # 0..1. Vertical film-damage streaks.
    flicker: float = 0.0       # 0..1. Frame-to-frame brightness wobble.
    glow: float = 0.0          # 0..1. Lifts shadow detail -- "improved lighting".

    PRESETS = {
        # A named preset just fills in these fields -- set any of them
        # yourself afterwards to override just that one.
        "none": {},
        "clean": {"contrast": 1.03, "saturation": 1.0},
        "warm": {"saturation": 0.97, "contrast": 1.05, "lift": 0.015, "glow": 0.15},
        "old_film": {"grain": 0.35, "vignette": 0.25, "saturation": 0.9,
                    "contrast": 1.08, "lift": 0.03, "scratches": 0.25,
                    "flicker": 0.12},
        "projector": {"grain": 0.4, "vignette": 0.45, "saturation": 0.88,
                     "contrast": 1.1, "lift": 0.02, "scratches": 0.4,
                     "flicker": 0.18},
    }

    @staticmethod
    def parse(d: Any) -> "Look":
        d = d or {}
        base = dict(Look.PRESETS.get(str(d.get("preset", "none")), {}))
        base.update({k: v for k, v in d.items() if k != "preset"})
        return Look(
            grain=float(base.get("grain", 0.0)),
            vignette=float(base.get("vignette", 0.0)),
            saturation=float(base.get("saturation", 1.0)),
            contrast=float(base.get("contrast", 1.0)),
            lift=float(base.get("lift", 0.0)),
            scratches=float(base.get("scratches", 0.0)),
            flicker=float(base.get("flicker", 0.0)),
            glow=float(base.get("glow", 0.0)),
        )


# --------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------


def parse_time(v: Any) -> float:
    """Accepts 12.5, "12.5", "00:02:14.5" or "2:14.5". Returns seconds."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).strip().split(":")
    secs = 0.0
    for p in parts:
        secs = secs * 60.0 + float(p)
    return secs


@dataclass
class Shot:
    src: str
    duration: float | None = None    # seconds. For video, defaults to out-in.
    kind: str = "still"              # still | video  (detected from extension)

    # video only
    tin: float = 0.0
    tout: float | None = None
    speed: float = 1.0

    # camera
    move: str = "auto"
    focus: tuple[float, float] | None = None
    amount: float = 1.0              # scales the move. 0.5 = half as much.
    frm: Window | None = None        # explicit override
    to: Window | None = None
    ease: str = "sine_in_out"

    # Seconds of cross-dissolve INTO this shot from the one before it.
    # 0 is a straight cut, and a straight cut is right almost everywhere.
    # This exists for one job: softening the joins where a pause was cut
    # out of a take, where a hard cut on the same face reads as a stumble.
    dissolve: float = 0.0

    # Overrides the film's `fill` for this one shot. A photograph usually
    # crops happily -- there is space in it to lose -- while the clip of
    # somebody's face next to it does not, and mixing the two in one film
    # is the ordinary case.
    fill: str | None = None          # None = whatever the film says

    captions: list[Caption] = field(default_factory=list)
    note: str = ""                   # for humans and for me. Never rendered.
    id: str = ""

    VIDEO_EXT = kinds.VIDEO        # kept as an alias: film.yaml files in
                                  # the wild refer to Shot.VIDEO_EXT

    @staticmethod
    def parse(d: dict, index: int) -> "Shot":
        src = str(d["src"])
        kind = "video" if Path(src).suffix.lower() in Shot.VIDEO_EXT else "still"

        tin = parse_time(d.get("in", 0.0))
        tout = parse_time(d["out"]) if "out" in d else None

        duration = d.get("duration")
        duration = float(duration) if duration is not None else None
        if duration is None and kind == "video" and tout is not None:
            duration = (tout - tin) / float(d.get("speed", 1.0))
        if duration is None:
            duration = 5.0

        focus = d.get("focus")
        if focus is not None:
            focus = (float(focus[0]), float(focus[1]))

        return Shot(
            src=src,
            kind=kind,
            duration=duration,
            tin=tin,
            tout=tout,
            speed=float(d.get("speed", 1.0)),
            move=str(d.get("move", "auto")),
            focus=focus,
            amount=float(d.get("amount", 1.0)),
            frm=Window.parse(d["from"]) if "from" in d else None,
            to=Window.parse(d["to"]) if "to" in d else None,
            ease=str(d.get("ease", "sine_in_out")),
            dissolve=max(0.0, float(d.get("dissolve", 0.0))),
            fill=str(d["fill"]).lower() if "fill" in d else None,
            captions=[Caption.parse(c) for c in d.get("captions", [])],
            note=str(d.get("note", "")),
            id=str(d.get("id", f"s{index + 1:02d}")),
        )


# --------------------------------------------------------------------------
# What a project has lying around it
#
# A film.yaml does not have to say where its music is, or what the film
# is called. Both are found on the disk instead, so that the answer to
# "how do I put music on it" stays "drop a file in a folder".
# --------------------------------------------------------------------------


# How far past the end of its shot a caption has to run before trimming
# it is worth mentioning. Everything below this is arithmetic, not a
# decision: the bench writes caption times to a tenth of a second, and a
# shot's length comes out of two timecodes and a speed, so the two rarely
# land on the same number. Above this, a line somebody meant to be read
# is going to be on screen for noticeably less time, and they should hear
# about it. Well under the 0.4s a caption spends fading out either way.
TRIM_WORTH_SAYING = 0.25


def pretty_name(stem: str) -> str:
    """thought_experiment -> 'Thought Experiment'.

    A folder name and a filename are usually already the words somebody
    wanted; they are just wearing underscores.
    """
    words = re.split(r"[_\-]+", stem.strip())
    return " ".join(w.capitalize() for w in words if w)


def title_of(project: Path) -> str:
    """What this film is called when nobody has said. The folder's name."""
    return pretty_name(project.name)


def find_music(project: Path) -> str | None:
    """The background track, in the order things should be looked for:
    this film's own music/ folder first, then the shared shelf.

    The shelf is the point -- put one track there and every film you ever
    make has music, with no step in the middle. Returned as a path
    relative to the project where it is one, so that a film.yaml written
    out of this stays portable; the shelf is elsewhere on the disk, so
    that one comes back absolute and is resolved as such.
    """
    own = project / "music"
    if own.is_dir():
        found = sorted(p for p in own.iterdir()
                       if p.is_file() and p.suffix.lower() in kinds.AUDIO)
        if found:
            return found[0].relative_to(project).as_posix()

    from . import library
    shared = library.music()
    return shared.as_posix() if shared else None


def headers(path: Path) -> dict:
    """The top-level keys of a film.yaml, without loading the film.

    Film.load checks that every source file exists, which is right before
    a render and wrong everywhere else: the thumbnail should still build
    for a film whose footage is on a drive that is not plugged in, and
    the guide should still be able to say what shape the film is while
    somebody is halfway through hand-editing the shots.
    """
    try:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return d if isinstance(d, dict) else {}


@dataclass
class Film:
    fps: int = 24
    width: int = 1920
    height: int = 1080
    title: str = ""                   # the words on the thumbnail. Empty
                                      # means "the project's own name",
                                      # filled in by load() -- see there.
    audio: str | None = None
    audio_offset: float = 0.0
    music: str | None = None          # background bed, auto-trimmed to length
    music_volume: float = 0.6         # The level while NOBODY is talking.
                                      # It used to be 0.4, because one fixed
                                      # number had to be quiet enough to talk
                                      # over -- which left the music timid
                                      # through every stretch with no voice
                                      # in it. Ducking does that job now, so
                                      # this can be what it should be: the
                                      # music, playing.
    music_fade: float = 2.0           # seconds of fade in and out
    music_duck: float = 0.5           # 0..1. How hard the music gets out of
                                      # the way while anyone is talking.
                                      # 0 = never, it just sits at
                                      # music_volume the whole way through.
    keep_clip_audio: bool = True      # speech recorded in your video clips
    speech_lift: bool = True          # bring quiet speech up to a normal
                                      # level before anything is mixed under
                                      # it. A phone held at arm's length
                                      # records a voice about 30dB below a
                                      # mastered music track -- no music
                                      # setting can fix that; the voice has
                                      # to come up. False leaves it raw.
    loudness: float = -14.0           # LUFS the finished film is normalised
                                      # to. -14 is what the platforms use.
                                      # 0 leaves your levels exactly as they
                                      # came out of the mix.
    # What to do when the picture is not the shape of the frame.
    #
    # "crop" fills the frame and throws away the overflow. It is right
    # almost always, and it is what every film made before this did.
    #
    # "blur" keeps the picture whole on a blurred, enlarged copy of
    # itself. The case it exists for: a 16:9 webcam in a 9:16 film, where
    # cropping keeps 32% of the width and a person sitting close to the
    # camera loses both ears.
    #
    # fill_aspect is the shape of the sharp picture inside the blur, as
    # width/height. 1.0 is square. It is NOT "show the whole frame":
    # showing all of a 16:9 picture in a 9:16 film leaves the speaker
    # about a fifth of the height tall, which solves the cropping by
    # making them too small to see. Square keeps 56% of a 16:9 frame's
    # width instead of 32%, which is enough for a head and shoulders,
    # and still fills a useful amount of the screen.
    fill: str = "crop"                # crop | blur
    fill_aspect: float = 1.0          # width / height of the sharp part

    look: Look = field(default_factory=Look)
    shots: list[Shot] = field(default_factory=list)
    root: Path = field(default_factory=Path)
    notes: list[str] = field(default_factory=list)   # said by load(), not
                                                     # read from film.yaml

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.shots)

    def resolve(self, src: str) -> Path:
        """Paths in film.yaml are relative to the film.yaml itself."""
        p = Path(src)
        return p if p.is_absolute() else (self.root / p)

    @staticmethod
    def load(path: str | Path) -> "Film":
        path = Path(path).resolve()
        raw = path.read_text(encoding="utf-8")

        # The single most common hand-editing mistake, and PyYAML's own
        # message for it is baffling. Catch it first and say it plainly.
        for i, line in enumerate(raw.splitlines(), 1):
            if line[: len(line) - len(line.lstrip())].count("\t"):
                raise SystemExit(
                    f"film.yaml line {i}: this line is indented with a TAB.\n"
                    f"YAML only allows spaces. Replace the tab with 2 spaces.\n"
                    f"In Notepad++: Settings > Preferences > Language >\n"
                    f"tick 'Replace by space', then retype the indent."
                )

        try:
            d = yaml.safe_load(raw) or {}
        except yaml.YAMLError as exc:
            where = ""
            mark = getattr(exc, "problem_mark", None)
            if mark is not None:
                where = f" line {mark.line + 1}, column {mark.column + 1}"
            problem = getattr(exc, "problem", None) or "could not be parsed"
            raise SystemExit(
                f"film.yaml{where}: {problem}.\n"
                f"Usual causes: a missing space after a colon, a stray quote, "
                f"or an indent that does not line up with the line above."
            )

        if not isinstance(d, dict):
            raise SystemExit("film.yaml should start with keys like `fps:` "
                             "and `shots:`.")

        res = d.get("resolution", [1920, 1080])
        film = Film(
            fps=int(d.get("fps", 24)),
            width=int(res[0]),
            height=int(res[1]),
            title=str(d.get("title", "")),
            audio=d.get("audio"),
            audio_offset=float(d.get("audio_offset", 0.0)),
            music=d.get("music"),
            music_volume=float(d.get("music_volume", 0.6)),
            music_fade=float(d.get("music_fade", 2.0)),
            music_duck=max(0.0, min(1.0, float(d.get("music_duck", 0.5)))),
            keep_clip_audio=bool(d.get("keep_clip_audio", True)),
            speech_lift=bool(d.get("speech_lift", True)),
            loudness=float(d.get("loudness", -14.0)),
            fill=str(d.get("fill", "crop")).lower(),
            fill_aspect=float(d.get("fill_aspect", 1.0)),
            look=Look.parse(d.get("look")),
            shots=[Shot.parse(s, i) for i, s in enumerate(d.get("shots", []))],
            root=path.parent,
        )
        if not film.title:
            film.title = title_of(path.parent)
        if film.music is None:
            film.music = find_music(path.parent)
        film.validate()
        # A caption that runs past its shot is trimmed, not refused --
        # see trim_captions. The notes ride along on the film so that
        # whoever is about to render it can say what happened.
        film.notes = film.trim_captions()
        return film

    def validate(self) -> None:
        """Fail loudly and early, with a message that says what to fix.

        Only for things that cannot be rendered at all. A caption that
        runs past its shot is NOT one of them: the shot ends, the caption
        goes with it, and that is what the renderer does anyway. This
        used to refuse the whole film over it -- and the overrun was
        routinely six hundredths of a second, put there by `film caption`
        or by dragging a shot shorter in the bench. Being told that a
        thirty-six second film cannot be rendered because a subtitle is
        one and a half frames too long is the kind of thing that makes
        somebody close the laptop.
        """
        problems = []
        if not self.shots:
            problems.append("film.yaml has no shots.")
        for s in self.shots:
            p = self.resolve(s.src)
            if not p.exists():
                problems.append(f"[{s.id}] file not found: {p}")
            if s.duration <= 0:
                problems.append(f"[{s.id}] duration must be positive.")
        if problems:
            raise SystemExit(
                "film.yaml has problems:\n  - " + "\n  - ".join(problems)
            )

    def trim_captions(self) -> list[str]:
        """Bring every caption back inside the shot it sits on.

        Returns a note for each one that was long enough for the change
        to be visible -- worth saying, because a line you meant to be
        read is going to be on screen for less time than you asked. A
        rounding overrun is silent; there is nothing to tell anybody.
        """
        notes = []
        for s in self.shots:
            for c in s.captions:
                room = s.duration - c.at
                if room <= 0:
                    # It starts after the shot has ended. Nothing can be
                    # done with that except not draw it.
                    if c.dur > 0:
                        notes.append(f'[{s.id}] caption {c.text!r} starts '
                                     f'after the shot ends -- not shown.')
                    c.dur = 0.0
                elif c.at + c.dur > s.duration:
                    if c.at + c.dur > s.duration + TRIM_WORTH_SAYING:
                        notes.append(
                            f'[{s.id}] caption {c.text!r} cut short by '
                            f'{c.at + c.dur - s.duration:.1f}s -- the shot '
                            f'ends first.')
                    c.dur = room
        return notes
