"""
scaffold.py  --  write a first film.yaml from what ingest found.

Deliberately not clever. It gives you a complete, valid, watchable film
in one command, so your first render never depends on anyone else. Then
you change the numbers -- which is the whole point of the system.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from . import kinds, segment
from .moves import choose_moves
from .record import REC_SPEED, is_recording
from .spec import VOICE_TAIL, Caption, Shot, pretty_name


# A person talking to a lens is not a photograph. There is nowhere to
# drift TO -- their face is the interesting part for the whole shot -- so
# the camera frames it and then behaves. A push_in on a talking head
# walks into their nose; a tilt_up on one cropped to 9:16 takes the top
# of their head off. Static and the two drifts, alternating so that no
# two neighbours share a family, and nothing that changes the framing
# enough to lose an ear.
TALKING_MOVES = ["static", "drift_right", "static", "drift_left"]
TALKING_AMOUNT = 0.6         # even the drifts, gentler than on a still


def _video_focus(entry: dict) -> tuple[float, float]:
    """Where the speaker is, as found by ingest. Falls back to the middle
    only when the clip gave nothing to go on."""
    f = entry.get("focus")
    return (float(f[0]), float(f[1])) if f else (0.5, 0.5)


def _speed_for(path: str) -> float:
    """A take you shot with `film record` comes in slightly brisk.

    It is a number in film.yaml, not something done to the file: the
    original in media/ stays exactly the speed you spoke at, and if 1.2
    is wrong for a particular take you change one digit. Anything you
    dropped in from a camera or a phone is left alone -- this is a
    correction for talking to a lens, not a house style.
    """
    return REC_SPEED if is_recording(Path(path).stem) else 1.0

AUDIO_EXT = kinds.AUDIO

STILL_SECONDS = 4.5
FACE_SECONDS = 5.5          # a face holds attention longer. Give it room.
VIDEO_SECONDS = 4.0          # a sample from a SILENT clip. B-roll length.
MAX_SEGMENTS_PER_VIDEO = 6
TALK_WHOLE_MAX = 240.0       # a take longer than this is SPLIT (never shortened)
SOUND_FLOOR = 0.03           # audible for less than this fraction = B-roll
                             # Deliberately tiny. This is "did anyone record
                             # sound", not "is this mostly talking". Someone
                             # speaking to camera with real pauses can be
                             # audible only a tenth of the time -- a 76s take
                             # with twelve transcribed lines measured 0.118,
                             # and a 0.12 floor threw the whole thing away.
PAUSE_DROP = 1.5             # dead air longer than this is cut out
BREATH = 0.3                 # left either side of a cut, so words survive
MIN_PIECE = 0.8              # a fragment shorter than this is not a shot
MAX_TRIM = 0.35              # never cut away more than this much of a take
DISSOLVE = 0.3               # softens ONLY the joins where a pause was cut
OPENER_CLOSER_SECONDS = 3.0  # a title-card image, held, is usually brief

# The opening card -- the film's name over the same picture as the
# thumbnail. Long enough to read a title and settle, short enough that
# nobody reaches for the scrub bar: four seconds is about two beats
# after you have finished reading. It is written into film.yaml as an
# ordinary shot, so it is a number you can change and a block you can
# delete, like everything else in there.
TITLE_CARD_SECONDS = 4.0
# On a vertical film -- a Short -- the first sentence is the hook, and a
# still title held for four seconds is where people scroll away. Half of
# it. Chosen by reasoning, not measured on an audience.
SHORT_TITLE_CARD_SECONDS = 2.0
QUOTE_SECONDS = 5.0          # a quote needs to be READ, not glanced at

# Filename hints, checked so you can drop files in fast without opening
# film.yaml at all. None of these are required -- unhinted files just
# fall back to plain alphabetical order.
#
#   00_thing.jpg, 01_thing.jpg    explicit numbered order (checked first)
#   1thing.jpg                    the separator is optional -- see below
#   open_thing.jpg                use as the opening shot
#   close_thing.jpg               use as the closing shot
#   open_close_thing.jpg          use the SAME image to open AND close
#   quote_thing.jpg                held longer, centered text if titled
#   rec_20260828-1014.mp4          made by `film record` -- comes in at
#                                  REC_SPEED, because talking to a lens
#                                  is slower than talking to a person
#
# A file can only be recognized by one of these -- the most specific
# match wins (open_close over open, a number over a word-hint).
# A leading run of up to three digits is the order you asked for, and
# whatever separates it from the name -- an underscore, a dot, a dash, a
# space, or nothing at all -- is not part of the request. This used to
# demand a separator, and Jacek's three pictures, `1declaration…`,
# `2declaration of love` and `3_declaration…`, came out 3, 1, 2: only the
# third was read as numbered, so it went first and the other two followed
# alphabetically behind it. The file the machine writes promises that
# `00_ 01_` orders files; it was keeping that promise for one spelling of
# it.
#
# `(?!\d)` is what keeps a date or a camera counter out of this:
# `20260917.jpg` and `IMG_0042.jpg` are not somebody asking for position
# 202 or 42.
_NUM_PREFIX = re.compile(r"^(\d{1,3})(?!\d)[_.\-\s]*")


def _hint(stem: str) -> tuple[str | None, int | None, str]:
    """Returns (role, explicit_number, clean_stem). role is one of:
    None, 'open', 'close', 'open_close', 'quote'.

    A number and a role are independent -- `00_open_close_x.png` gets
    BOTH: shown first (the number) AND treated as the opener/closer (the
    role). Strip the number first, then look for a role in what's left.
    """
    stem_no_num = stem
    num = None
    m = _NUM_PREFIX.match(stem.lower())
    if m:
        num = int(m.group(1))
        stem_no_num = stem[m.end():]

    low = stem_no_num.lower()
    for prefix, role in (("open_close_", "open_close"), ("openclose_", "open_close"),
                        ("open_", "open"), ("close_", "close"),
                        ("quote_", "quote")):
        if low.startswith(prefix):
            return role, num, stem_no_num[len(prefix):]
    return None, num, stem_no_num


def _title_from_stem(stem: str) -> str:
    """thought_experiment -> 'Thought Experiment'. Used for quote/title
    cards, where the filename is often already the words you want. The
    same rule names the film itself -- see spec.pretty_name."""
    return pretty_name(stem)


def is_talking(entry: dict) -> bool:
    """Did someone record sound on this clip?

    Not "is this speech" -- we cannot know that without transcribing, and
    we are not going to. Sound at all is the right test, because the two
    mistakes are not equal. Keep a clip whole that turned out to be wind,
    and you have a film that runs long; you see it in the peek and you
    trim a number. Sample four seconds out of a clip she was talking over,
    and the sentence that mattered is gone -- and nothing on screen tells
    her it was ever there.
    """
    snd = entry.get("sound") or {}
    return bool(snd.get("has")) and float(snd.get("ratio", 0.0)) >= SOUND_FLOOR


def talking_segments(dur: float, snd: dict) -> list[tuple[float, float]]:
    """Keep every word. Drop the dead air between them.

    Three things happen here, in order:

      1. The lead-in and the tail go -- the seconds of fumbling before you
         start and after you finish.
      2. Any pause longer than PAUSE_DROP goes, leaving BREATH either side
         so it lands on a natural beat instead of clipping a word. Short
         pauses stay: speech without them sounds panicked.
      3. Anything still longer than TALK_WHOLE_MAX is split at a remaining
         pause, so one long take can carry more than one camera move.

    What comes back is a list of consecutive in/out pairs. Every one of
    them is a separate shot, which is what gives you the reframe on each
    cut -- and why it reads as an edit rather than a glitch.
    """
    a = max(0.0, float(snd.get("in", 0.0)) - BREATH)
    b = min(dur, float(snd.get("out", dur)) + BREATH)
    if b - a < 1.0:                          # nothing sensible to trim to
        a, b = 0.0, dur

    inner = [(s, e) for s, e in snd.get("quiet", []) if a < s and e < b]

    kept: list[tuple[float, float]] = []
    cursor = a
    for s, e in inner:
        if e - s < PAUSE_DROP:               # a breath, not dead air. Keep it.
            continue
        end = s + BREATH
        if end - cursor >= MIN_PIECE:
            kept.append((cursor, end))
        cursor = max(cursor, e - BREATH)
    if b - cursor >= MIN_PIECE:
        kept.append((cursor, b))
    if not kept:
        kept = [(a, b)]

    # If that wanted to throw away half the take, the detection is wrong,
    # not the take. A softly spoken passage reads as silence to any level
    # threshold, and losing it is far worse than leaving a slow patch in.
    # When in doubt, keep everything.
    if sum(y - x for x, y in kept) < (b - a) * (1.0 - MAX_TRIM):
        kept = [(a, b)]

    # Split anything still too long, at the pauses we chose to keep.
    out: list[tuple[float, float]] = []
    for x, y in kept:
        while y - x > TALK_WHOLE_MAX:
            here = [s for s, e in inner if x + TALK_WHOLE_MAX * 0.6 < s < y]
            if not here:
                break
            cut = min(here, key=lambda s: abs(s - (x + TALK_WHOLE_MAX)))
            out.append((x, cut))
            x = cut
        out.append((x, y))

    return [(round(x, 2), round(y, 2)) for x, y in out if y - x >= MIN_PIECE]


def video_segments(entry: dict) -> list[tuple[float, float]]:
    """Turn a clip into usable in/out pairs.

    A clip with sound on it is kept (see `is_talking`). A silent clip is
    B-roll, and gets sampled: if it has hard cuts we respect them, and if
    it doesn't -- normal for handheld footage, and for anything long and
    continuous -- we sample along it instead. Roughly one shot per minute
    of source, so a ten minute clip yields several candidates, not one.
    """
    dur = float(entry.get("duration") or 0.0)
    if dur < 1.5:
        return []
    if is_talking(entry):
        return talking_segments(dur, entry["sound"])
    cuts = [c for c in entry.get("cuts", []) if 0.0 < c < dur]
    bounds = [0.0] + cuts + [dur]

    budget = max(1, min(MAX_SEGMENTS_PER_VIDEO, round(dur / 60.0) + 1))

    candidates: list[tuple[float, float]] = []
    for a, b in zip(bounds, bounds[1:]):
        seg = b - a
        if seg < 2.0:                          # too short to be a shot
            continue
        # More shots from longer segments, proportionally.
        k = max(1, min(budget, int(seg // 45) + 1))
        for j in range(k):
            centre = a + seg * (j + 0.5) / k
            start = max(a + 0.3, centre - VIDEO_SECONDS / 2)
            end = min(start + VIDEO_SECONDS, b - 0.2)
            if end - start >= 1.5:
                candidates.append((round(start, 2), round(end, 2)))

    # Keep the longest, but present them in timeline order.
    candidates.sort(key=lambda s: s[1] - s[0], reverse=True)
    return sorted(candidates[:budget])


def tc(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f'"{int(m):02d}:{s:05.2f}"'


def build(project: Path, seed: int = 0, target: float | None = None) -> str:
    mpath = project / "analysis" / "manifest.json"
    if not mpath.exists():
        raise SystemExit("Run `uv run film ingest` first.")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))

    # A narration track lying in media/. Never one from _discarded/ or
    # _unreadable/ -- a take set aside is not the film's soundtrack.
    media_dir = project / "media"
    audio = next((p for p in sorted(media_dir.rglob("*"))
                  if p.suffix.lower() in AUDIO_EXT
                  and not kinds.is_aside(p, media_dir)), None)

    # Read the filename hint for every still up front -- this decides
    # ORDER (explicit numbers first, else alphabetical) and ROLE
    # (opener / closer / quote / plain), before any shots get built.
    tagged = []
    for e in manifest["media"]:
        stem = Path(e["path"]).stem
        role, num, clean = _hint(stem)
        tagged.append({"entry": e, "role": role, "num": num, "clean": clean})

    numbered = sorted((t for t in tagged if t["num"] is not None),
                      key=lambda t: t["num"])
    unnumbered = [t for t in tagged if t["num"] is None]
    # Openers first, closers last, everything else keeps its order --
    # this is what lets you drop files in any which way and still get
    # "title card, talking, quote, title card again" for free. A numbered
    # file's position is exactly what you typed, full stop -- the number
    # is a stronger signal than the role, so numbered opens/closes are
    # NOT re-sorted, only unnumbered ones are.
    openers = [t for t in unnumbered if t["role"] in ("open", "open_close")]
    closers = [t for t in unnumbered if t["role"] == "close"]
    middle = [t for t in unnumbered if t["role"] not in
             ("open", "close", "open_close")]
    ordered = numbered + openers + middle + closers
    # open_close: the SAME file also plays at the very end -- true
    # whether it got there by role (unnumbered) or by an explicit number.
    for t in unnumbered:
        if t["role"] == "open_close":
            ordered.append(t)
    for t in numbered:
        if t["role"] == "open_close":
            ordered.append(t)

    # `quote_` has no natural position relative to other unnumbered
    # content -- unlike open/close, "before or after the talking?" isn't
    # something a filename alone can answer. Flag it rather than guess.
    ambiguous_quotes = (len(numbered) == 0 and
                       any(t["role"] == "quote" for t in middle) and
                       len(middle) > 1)

    # One file at a time, through the one function that knows what a file
    # becomes. See shots_for.
    shots: list[Shot] = []
    meta: list[dict] = []
    for t in ordered:
        made, made_meta = shots_for(t["entry"], len(shots) + 1)
        shots.extend(made)
        meta.extend(made_meta)

    if not shots:
        raise SystemExit("No usable media found. Is anything in media/ ?")

    # A narration over photographs, with no script to cut it by: give
    # each picture its own piece of it, cut at the longest pauses. That
    # is the only way anything in film.yaml can say which picture goes
    # with which words -- see cut_into_slides.
    #
    # Photographs only. A film that also has footage keeps the flat
    # `audio:` track: a clip carries its own sound, and cutting one
    # narration across pictures and clips alike is a bigger decision
    # than `init` should be making on its own.
    slide_notes: list[str] = []
    if audio and all(s.kind == "still" for s in shots):
        slide_notes = cut_into_slides(shots, meta, project, audio)
    slides = bool(slide_notes)

    target_notes: list[str] = []
    if audio and not slides:
        target_notes += stretch_to_narration(
            shots, meta, narration_seconds(audio) + NARRATION_FADE_ROOM)
    if target:
        target_notes += fit_to_target(shots, meta, float(target))
        keep = [(s, m) for s, m in zip(shots, meta) if s.duration > 0]
        shots = [s for s, _ in keep]
        meta = [m for _, m in keep]
        for i, s in enumerate(shots, 1):        # renumber after any drops
            s.id = f"s{i:02d}"

    # Assign varied moves -- never two of the same family back to back.
    # Opener/closer/quote shots already have a fixed move and are skipped.
    choose_moves(shots, seed=seed)

    L = []
    L.append("# Written by `film init`. Everything here is a starting point.")
    L.append("# Change the numbers. That is what this file is for.")
    L.append("#")
    L.append("# Filename hints `init` understood, if you used any:")
    L.append("#   00_ 01_ ...     explicit order")
    L.append("#   open_ close_    which shot opens / closes the film")
    L.append("#   open_close_     the SAME image opens AND closes it")
    L.append("#   quote_          held longer, filename becomes a centered title")
    L.append("#")
    L.append("#   uv run film peek    seconds    -- is the ORDER right?")
    L.append("#   uv run film draft   <1 min     -- does the MOTION feel right?")
    L.append("#   uv run film final   minutes    -- ship it")
    L.append("")
    L.append("fps: 24")
    vertical = (project / ".vertical").exists()
    if vertical:
        L.append("resolution: [1080, 1920]   # vertical, for YouTube Shorts")
    else:
        L.append("resolution: [1920, 1080]")

    # Built here, before `audio_offset` is decided, rather than where it
    # is written into `shots:` below -- the narration needs to know
    # whether there IS a card, and how long it holds, before it can know
    # where to start.
    card_block = title_card_block(project, vertical)
    card_seconds = ((SHORT_TITLE_CARD_SECONDS if vertical else TITLE_CARD_SECONDS)
                    if card_block else 0.0)

    if audio and slides:
        # No `audio:` here on purpose. It would play the whole narration
        # flat under the film IN ADDITION to the pieces on the slides --
        # every word said twice, a beat apart.
        L.append("# Each picture carries its own piece of")
        L.append(f"# {audio.relative_to(project).as_posix()} -- see `voice:` below.")
    elif audio:
        L.append(f'audio: {audio.relative_to(project).as_posix()}')
        if card_seconds:
            L.append(f"audio_offset: {card_seconds:.1f}   "
                     f"# the narration waits for the opening card")
        else:
            L.append("audio_offset: 0.0")
    else:
        L.append("# audio: media/voiceover.mp3   # optional separate narration")
    L.append("# title: the words on the thumbnail. Left out, the film is")
    L.append("#        called what its folder is called.")
    L.append("# music: found on its own -- this project's music/ folder if it")
    L.append("#        has one, otherwise your library/music/ folder.")
    L.append("music_volume: 0.6      # the level when nobody is talking")
    L.append("music_fade: 2.0        # seconds of fade in and out")
    L.append("music_duck: 0.5        # how far the music drops while you talk")
    L.append("                       # 0 = never drops. 1 = gets right out of the way")
    L.append("")
    L.append("look:")
    L.append("  preset: old_film      # clean | warm | old_film | projector")
    L.append("  glow: 0.25            # lifts shadows -- better lighting")
    L.append("")
    L.append("# Uncomment if a wide clip is losing too much to a tall frame.")
    L.append("# `blur` keeps the picture whole on a blurred copy of itself")
    L.append("# instead of cropping it. fill_aspect is the shape of the sharp")
    L.append("# part: 1.0 square, 0.8 taller and bigger, 1.33 shorter and safer.")
    L.append("# fill: blur")
    L.append("# fill_aspect: 1.0")
    L.append("")
    L.extend(bokeh_lines(segment.missing_model() is None))
    L.append("")
    L.append("shots:")
    L.extend(card_block)

    for s, m in zip(shots, meta):
        L.extend(shot_block(s, m))

    L.append("")
    total = sum(s.duration for s in shots)
    L.append(f"# {len(shots)} shots, about {total:.0f} seconds.")
    for note in target_notes + slide_notes:
        L.append(note)
    if ambiguous_quotes:
        L.append("#")
        L.append("# NOTE: a quote_ card was placed by guesswork among other")
        L.append("# unnumbered files -- its position (before/after other shots)")
        L.append("# was NOT something the filename could tell me. Check the")
        L.append("# order above; if it's wrong, either reorder the shots: blocks")
        L.append("# below, or rename files 00_, 01_, 02_... and run init again.")
    # Not on a slide film. The words ARE the film there, and `caption`
    # is the next step the footer above already names.
    if not slides and not any(m.get("role") == "quote" for m in meta):
        L.extend(NO_CAPTIONS_YET)
    L.append("")
    return "\n".join(L)


def bokeh_lines(model_present: bool) -> list[str]:
    """Bokeh is on in every new film, and says so in film.yaml.

    Written into the file rather than made the code's default, so it can
    be seen and set to 0, and so films made before it keep looking the
    way they were watched. Without the model it is written commented out:
    a fresh machine's first render must not stop over a look.
    """
    L = ["# The room behind you softly blurred, you sharp -- on your own",
         "# recordings (rec_*) only. 0 = off, 2 = twice as soft. About +45%",
         "# render time. Barely shows in a vertical close-up: the crop is",
         "# nearly all face. Another clip can ask for it with its own `bokeh:`."]
    if model_present:
        L.append("bokeh: 1")
    else:
        L.append(f"# bokeh: 1   <- needs models/{segment.MODEL_FILE}, "
                 f"see models/README.md")
    return L


def title_card_block(project: Path, vertical: bool) -> list[str]:
    """The opening shot: the film's name over the thumbnail picture.

    Written only when there is a picture to write it on -- which, once
    the library has one wide and one tall backdrop in it, is always, for
    every film, with nobody doing anything.

    `static` and nothing else. Every other move scales into the frame,
    and the frame is a title: push in on it by even a few percent and
    the words start losing their edges. It also earns its keep as a
    stillness before the first person speaks.
    """
    from . import cover

    w, h = (1080, 1920) if vertical else (1920, 1080)
    if cover.build_card(project, w, h) is None:
        return []
    return [
        "",
        "  - id: s00",
        f"    src: {cover.card_src(project)}",
        f"    duration: "
        f"{SHORT_TITLE_CARD_SECONDS if vertical else TITLE_CARD_SECONDS:.1f}",
        "    move: static",
        '    note: "the opening card -- the same picture and the same words',
        '      as the thumbnail, so clicking the miniature lands you on the',
        '      frame you clicked. Made from your library; delete this whole',
        '      block if you would rather open on yourself talking."',
    ]


def shot_block(s: Shot, m: dict) -> list[str]:
    """One shot, as the lines that go in film.yaml.

    Its own function because two callers need it: writing a film from
    scratch, and appending the footage you shot after lunch to a film you
    have already tuned.
    """
    L: list[str] = []
    e, role = m["entry"], m.get("role")
    L.append("")
    L.append(f"  - id: {s.id}")
    L.append(f"    src: {s.src}")
    if s.kind == "video":
        L.append(f"    in: {tc(m['in'])}")
        L.append(f"    out: {tc(m['out'])}")
        if abs(s.speed - 1.0) > 1e-3:
            L.append(f"    speed: {s.speed}              # 1.0 is the speed "
                     f"you actually spoke at")
    elif s.voice:
        # A slide: the picture from `src`, the words from `voice`, and
        # in/out their times inside it. No `duration:` -- it defaults to
        # the words plus a breath, which is what a slide is for. Write
        # one to hold the picture longer; the words do not stretch.
        L.append(f"    voice: {s.voice}")
        L.append(f"    in: {tc(s.tin)}")
        L.append(f"    out: {tc(s.tout)}")
    else:
        L.append(f"    duration: {s.duration:.1f}")
    L.append(f"    move: {s.move}")
    if abs(s.amount - 1.0) > 1e-3:
        L.append(f"    amount: {s.amount}            # how much of the move "
                 f"to use. 0 = none")
    L.append(f"    focus: [{s.focus[0]:.3f}, {s.focus[1]:.3f}]")
    if s.dissolve:
        L.append(f"    dissolve: {s.dissolve}      # blends in from the "
                 f"shot before. 0 = a hard cut")
    if role in ("open", "open_close"):
        L.append('    note: "opener -- held still, deliberately brief"')
    elif role == "close":
        L.append('    note: "closer"')
    elif role == "quote":
        L.append('    note: "quote card -- title from filename"')
    elif m.get("slide"):
        L.append(f'    note: "picture {m['part']} of {m['parts']} -- holds '
                 f'while these words are said"')
    elif m.get("talking"):
        if m["parts"] > 1:
            note = (f"part {m['part']} of {m['parts']} -- one take with "
                    f"the long pauses cut out. Every word is kept")
        else:
            note = ("kept whole -- there is sound on this one, so none "
                    "of what you said is cut. Trim in:/out: if it drags")
        L.append(f"    note: {quoted(note)}")
    elif e.get("focus_from") == "face":
        L.append("    note: \"face detected -- given longer screen time\"")
    elif e.get("from"):
        L.append(f"    note: {quoted('converted from ' + Path(e['from']).name)}")
    if s.captions:
        L.append("    captions:")
        for c in s.captions:
            L.append(f"      - text: {quoted(c.text)}")
            L.append(f"        at: {c.at}")
            L.append(f"        dur: {c.dur}")
            L.append(f"        pos: {c.pos}")
    return L


MIN_SHOT = 2.0               # no still is worth less screen time than this

# Room left after the narration ends, so the music has somewhere to fade
# out into rather than being cut off on the last word. Same number as
# Film.music_fade's own default (spec.py) -- if that default moves, this
# should move with it.
NARRATION_FADE_ROOM = 2.0


def stretch_to_narration(shots: list[Shot], meta: list[dict],
                         target: float) -> list[str]:
    """Grow the photographs so the film covers a narration longer than
    they are. The inverse of fit_to_target's shrink -- and deliberately
    not the same function.

    fit_to_target's target is a CEILING for a Short: a film already
    under it is left alone, however far under
    (test_a_target_that_is_already_met_changes_nothing in
    test_editing_rules.py runs it at 300s against 18s of stills and
    expects nothing to move). This target is a FLOOR the narration
    needs met. They are not the same kind of number -- "no more than"
    and "at least" -- and making one function serve both would have
    made that test wrong.

    Only ever touches photographs. A video clip is stretched by slowing
    it down, which is record.REC_SPEED's decision to make on a take,
    not a duration target's to make silently on whatever clip is in
    the film.
    """
    notes: list[str] = []
    total = sum(s.duration for s in shots)
    if total >= target:
        return notes
    photos = [i for i, m in enumerate(meta)
             if m["entry"].get("kind") == "still"]
    photo_total = sum(shots[i].duration for i in photos)
    if photo_total <= 0:
        return notes
    room = target - (total - photo_total)
    factor = room / photo_total
    for i in photos:
        shots[i].duration *= factor
    notes.append(f"# Photographs held longer -- {room:.0f}s of pictures in "
                 f"all -- to cover the narration to its end.")
    return notes


def cut_at_pauses(start: float, end: float, quiet: list,
                  pieces: int) -> list[tuple[float, float]]:
    """Cut a narration into `pieces` consecutive windows, at its longest
    pauses. Pure -- hand it a pause list and it is arithmetic.

    The same idea as `talking_segments`, and the same constants: a cut
    takes BREATH off each side of the pause, so the words either side of
    it survive and the join lands on a natural beat. What falls in the
    gap between two windows is silence, and is not heard -- which is
    exactly what happens to a talking take today.

    The cuts are the LONGEST pauses, not the first ones: where somebody
    stopped for three seconds is where they finished a thought, and
    where they stopped for eight tenths is where they took a breath
    mid-sentence. A cut that would leave a picture on screen for less
    than MIN_SHOT is not made at all, and the next-longest pause is
    tried instead -- one enormous pause right after the first word is
    the end of a false start, not the end of a paragraph.

    Fewer pauses than asked-for cuts means fewer pieces. The caller is
    handed what it got and says so; inventing empty slides to reach a
    number would put a photograph on screen with nothing said over it.
    """
    a = max(0.0, start - BREATH)
    b = end + BREATH
    inner = sorted(((s, e) for s, e in quiet if a < s and e < b),
                   key=lambda p: p[1] - p[0], reverse=True)

    cuts: list[tuple[float, float]] = []
    for s, e in inner:
        if len(cuts) >= pieces - 1:
            break
        trial = sorted(cuts + [(s, e)])
        starts = [a] + [y - BREATH for _x, y in trial]
        ends = [x + BREATH for x, _y in trial] + [b]
        if all(hi - lo >= MIN_SHOT for lo, hi in zip(starts, ends)):
            cuts = trial

    out: list[tuple[float, float]] = []
    cursor = a
    for s, e in cuts:
        out.append((round(cursor, 2), round(s + BREATH, 2)))
        cursor = e - BREATH
    out.append((round(cursor, 2), round(b, 2)))
    return out


def narration_seconds(path: Path) -> float:
    """How long the narration file is. Its own function so a test can
    stand in for it without decoding anything."""
    from .audio import _dur
    return _dur(path)


def narration_pauses(path: Path) -> tuple[float, float, list]:
    """(first word, last word, the pauses between) for a narration file.

    The same measurement `ingest` already makes on every clip -- window
    RMS, the room and the voice found in this take's own distribution,
    the line put between them. See ingest.quiet_stretches for why it is
    not `silencedetect`. Run here on a standalone audio file, which
    ingest itself never looks at: its manifest is pictures and clips.

    Its own function, and the only impure part of the slide path, so
    that everything above it can be tested on a pause list.
    """
    from . import ingest as ingest_mod
    dur = narration_seconds(path)
    snd = ingest_mod.detect_sound(path, dur)
    if not snd.get("has"):
        return 0.0, dur, []
    return (float(snd.get("in", 0.0)), float(snd.get("out", dur)),
            [(float(s), float(e)) for s, e in snd.get("quiet", [])])


def cut_into_slides(shots: list[Shot], meta: list[dict], project: Path,
                    audio: Path) -> list[str]:
    """Give each photograph its own piece of the narration.

    Turns plain stills into SLIDES -- `voice:`, `in:`, `out:` -- in the
    order they are already in, and hands back the footer lines saying
    what it did. An empty list back means it did not do it, and the
    caller keeps the flat `audio:` track.
    """
    start, end, quiet = narration_pauses(audio)
    if end - start < MIN_SHOT:
        return []
    pieces = cut_at_pauses(start, end, quiet, len(shots))
    if not pieces:
        return []

    rel = audio.relative_to(project).as_posix()
    for i, (s, (a, b)) in enumerate(zip(shots, pieces)):
        s.voice = rel
        s.tin, s.tout = a, b
        s.duration = (b - a) + VOICE_TAIL
        meta[i]["slide"] = True
        meta[i]["part"] = i + 1
        meta[i]["parts"] = len(pieces)
    # More pictures than pieces: the ones past the end have no words and
    # would sit there in silence. Left as plain photographs, at the end.
    for s in shots[len(pieces):]:
        s.voice = None

    total = narration_seconds(audio)
    L = ["#",
         f"# {len(pieces)} slide(s), one per picture, each holding its own "
         f"piece of",
         f"# the {total:.0f}s narration. Each `in:`/`out:` is that picture's "
         f"words, on",
         "# the narration's own clock. Move a shot and its words move with it;",
         "# swap `src:` to put a different picture under the same words; hold",
         "# one longer with `duration:` and the words stay where they were said."]
    if len(pieces) < len(shots):
        L.append(f"# {len(shots) - len(pieces)} picture(s) came after the "
                 f"last words and are held silent.")
    L += ["#"] + list(SLIDES_GUESSED)
    return L


# Where the cuts came from, written into the file so that the answer to
# "why is this picture up for thirty seconds" is in the file itself.
# `recut_slides` swaps the first for the second, the way `add_captions`
# takes out NO_CAPTIONS_YET: after a script has said where the paragraphs
# are, a file still claiming the cuts were guessed is simply wrong.
SLIDES_GUESSED = (
    "# Where the cuts go was GUESSED, from where you paused. To say it",
    "# exactly, put your words in script.txt, one paragraph per picture,",
    "# and run `uv run film caption --apply`.",
)
SLIDES_BY_SCRIPT = (
    "# Cut by the paragraphs of script.txt -- one paragraph, one picture.",
    "# Change the paragraphs there and run `uv run film caption --apply`",
    "# again, or move these `in:`/`out:` numbers by hand.",
)


def fit_to_target(shots: list[Shot], meta: list[dict],
                  target: float) -> list[str]:
    """Bring the film down to `target` seconds. Never by cutting speech.

    Twenty-five photographs at four and a half seconds each is a two
    minute film, and a two minute film is not a Short -- nobody reaches
    the end of it. So: shorten the photographs, then drop the weakest
    ones, and if that still is not enough, say so rather than reaching
    for the one thing that must not be touched.

    What you said is never shortened to hit a number. If your talking
    alone is longer than the target, the target loses.
    """
    notes: list[str] = []
    talking = {i for i, m in enumerate(meta) if m.get("talking")}
    spoken = sum(shots[i].duration for i in talking)
    flex = [i for i in range(len(shots)) if i not in talking]

    if sum(s.duration for s in shots) <= target:
        return notes

    if spoken >= target:
        for i in flex:
            shots[i].duration = MIN_SHOT
        notes.append(f"# You talk for {spoken:.0f}s, which is already past the "
                     f"{target:.0f}s target -- so the pictures were cut to the "
                     f"bone and nothing you said was touched.")
        return notes

    # 1. Shorten the pictures proportionally, down to a floor.
    room = target - spoken
    flex_total = sum(shots[i].duration for i in flex)
    if flex_total > 0:
        factor = room / flex_total
        for i in flex:
            shots[i].duration = max(MIN_SHOT, shots[i].duration * factor)

    # 2. Still over? Drop the least missable pictures, one at a time.
    # A face, an opener, a closer and a quote card all earn their place;
    # a plain photograph in the middle of a run does not.
    def droppable(i: int) -> bool:
        m = meta[i]
        return (m.get("role") not in ("open", "close", "open_close", "quote")
                and m["entry"].get("focus_from") != "face")

    dropped = 0
    while sum(s.duration for s in shots) > target:
        candidates = [i for i in flex if droppable(i)]
        if not candidates:
            break
        i = candidates[len(candidates) // 2]     # from the middle of the run
        flex.remove(i)
        shots[i].duration = 0.0                  # marked; removed below
        dropped += 1

    if dropped:
        notes.append(f"# {dropped} photograph(s) left out to reach the "
                     f"{target:.0f}s target. They are still in media/ -- "
                     f"raise the target, or add them back by hand.")
    over = sum(s.duration for s in shots if s.duration > 0)
    if over > target + 0.5:
        notes.append(f"# Could not get under {target:.0f}s without cutting "
                     f"into speech or below {MIN_SHOT}s a picture. "
                     f"This is {over:.0f}s.")
    return notes


def shots_for(entry: dict, first_id: int,
              run: int | None = None) -> tuple[list[Shot], list[dict]]:
    """The shot(s) one media file becomes.

    The ONLY place that decides this. `build` used to hold a second copy
    of the whole thing, and the two had already drifted apart: the copy
    in `build` stepped through TALKING_MOVES on the running length of the
    WHOLE film, this one on the length of its own little list. So `film
    init` and `film go` (which appends through here) gave the same clip
    different camera moves, and every future change of taste had to be
    made twice or be half made.

    `run` is how many shots the film already has, which is what the
    talking-head move rotation steps on. It defaults to `first_id - 1`,
    which is the same thing whenever ids are simply counted from one.
    """
    shots, meta = [], []
    stem = Path(entry["path"]).stem
    role, _num, clean = _hint(stem)
    run = (first_id - 1) if run is None else run

    if entry["kind"] == "still":
        if role in ("open", "close", "open_close"):
            dur, mv = OPENER_CLOSER_SECONDS, "static"
        elif role == "quote":
            dur, mv = QUOTE_SECONDS, "static"
        else:
            dur = FACE_SECONDS if entry.get("focus_from") == "face" else STILL_SECONDS
            mv = "auto"
        s = Shot(src=entry["path"], kind="still", duration=dur, move=mv,
                 focus=tuple(entry.get("focus", (0.5, 0.5))),
                 id=f"s{first_id:02d}")
        if role == "quote":
            s.captions.append(Caption(text=_title_from_stem(clean), at=0.3,
                                      dur=max(1.0, dur - 0.6), pos="center"))
        shots.append(s)
        meta.append({"entry": entry, "role": role})
    else:
        segments = video_segments(entry)
        talking = is_talking(entry)
        spd = _speed_for(entry["path"])
        spot = _video_focus(entry)
        for k, (a, b) in enumerate(segments, 1):
            here = run + len(shots)
            shots.append(Shot(src=entry["path"], kind="video",
                              duration=(b - a) / spd,
                              tin=a, tout=b, speed=spd,
                              move=(TALKING_MOVES[here % len(TALKING_MOVES)]
                                    if talking else "auto"),
                              amount=TALKING_AMOUNT if talking else 1.0,
                              focus=spot,
                              id=f"s{first_id + len(shots):02d}",
                              dissolve=DISSOLVE if (talking and k > 1) else 0.0))
            meta.append({"entry": entry, "in": a, "out": b, "role": role,
                         "talking": talking, "part": k, "parts": len(segments)})
    return shots, meta


def append_new(project: Path, seed: int = 0) -> list[str]:
    """Add shots for media that arrived AFTER film.yaml was written.

    The point of this is that both halves are true at once: your edit is
    yours and nothing rewrites it, and footage you drop in later actually
    reaches the film. Before this existed the first won silently -- new
    clips were analysed, proxied, and then never mentioned again.

    Appended as text, at the end, so every comment and every number you
    tuned survives untouched.
    """
    from .spec import Film

    yml = project / "film.yaml"
    manifest = json.loads(
        (project / "analysis" / "manifest.json").read_text(encoding="utf-8"))

    film = Film.load(yml)
    have = {s.src for s in film.shots}
    fresh = [e for e in manifest["media"] if e["path"] not in have]
    if not fresh:
        return []

    next_id = len(film.shots) + 1
    shots: list[Shot] = []
    meta: list[dict] = []
    for e in fresh:
        s, m = shots_for(e, next_id + len(shots),
                         run=len(film.shots) + len(shots))
        shots.extend(s)
        meta.extend(m)
    if not shots:
        return []

    # Keep the no-two-alike rule running across the join, by handing
    # choose_moves the last shot that is already in the film.
    choose_moves([film.shots[-1]] + shots if film.shots else shots, seed=seed)

    before = yml.read_text(encoding="utf-8")
    lines = [before.rstrip("\n"), "",
             f"# --- added {len(shots)} shot(s) from footage that arrived later ---"]
    for s, m in zip(shots, meta):
        lines.extend(shot_block(s, m))
    lines.append("")
    yml.write_text("\n".join(lines), encoding="utf-8")

    try:
        Film.load(yml)                     # it has to still parse
    except SystemExit:
        yml.write_text(before, encoding="utf-8")
        raise SystemExit(
            "Could not add the new footage to film.yaml without breaking it, "
            "so nothing was changed. This happens if `shots:` is not the last "
            "thing in the file. Move any other settings above it, or run "
            "`uv run film go --rewrite` to start the edit over.")
    return [s.src for s in shots]


# --------------------------------------------------------------------------
# Putting captions into a film.yaml that a person has to go on reading
# --------------------------------------------------------------------------


def quoted(text: str) -> str:
    """A string as a YAML double-quoted scalar, with its letters intact.

    json.dumps quotes and escapes exactly the way YAML wants, which is
    why it is used -- but it also escapes every non-ASCII character, so
    `Kolobrzeg` with its proper letters came out as a row of \\u00f3.
    That parses back correctly and is unreadable, in a file whose entire
    purpose is being read by the person whose language it is in. The
    file is written and read as UTF-8 at both ends.
    """
    return json.dumps(str(text), ensure_ascii=False)


def _caption_lines(caps, indent: str) -> list[str]:
    L = [f"{indent}captions:"]
    for c in caps:
        L.append(f"{indent}  - text: {quoted(c.text)}")
        L.append(f"{indent}    at: {float(c.at):.2f}")
        L.append(f"{indent}    dur: {float(c.dur):.2f}")
        L.append(f"{indent}    pos: {c.pos}")
        if c.words:
            L.append(f"{indent}    words: {_seconds_list(c.words)}")
    return L


def _seconds_list(times) -> str:
    """[0.00, 0.41, 0.83] -- one short line, readable and hand-editable."""
    return "[" + ", ".join(f"{float(t):.2f}" for t in times) + "]"


# The footer `build` writes when a film has no captions. `add_captions`
# takes it out again, because after `film go` had put 48 captions in, the
# file still said they were left out.
NO_CAPTIONS_YET = (
    "# Speech captions are left out on purpose -- run",
    "# `uv run film caption` once you're happy with the shots,",
    "# or watch it once and add what actually needs saying.",
)


@dataclass
class SlideCut:
    """One slide as a script says it should be. `sid` is the shot this
    replaces, or "" for one that has to be added to the film."""
    sid: str
    src: str
    voice: str
    tin: float
    tout: float
    note: str = ""


def slide_cuts(film, paragraphs, windows) -> list["SlideCut"]:
    """Match the paragraphs somebody wrote to the pictures they have.

    Pure: `windows` is what `voice.paragraph_windows` measured, one per
    paragraph, None where a paragraph was never read out.

    Pictures go to paragraphs in order, unless a paragraph named one --
    `[3]` matches a picture whose filename starts with that number,
    `[3_declaration_of_love.png]` matches it outright.

    The two uneven cases, both of which happen the moment somebody
    rewrites a script without renaming files:

      more paragraphs than pictures -- the last picture is used again,
      and the extra slides are added to the film;
      more pictures than paragraphs -- the leftover pictures SHARE the
      last paragraph, its window divided between them. Not repeated:
      two slides quoting the same words would say them twice.
    """
    slides = [s for s in film.shots if s.voice]
    if not slides:
        return []
    voice_src = slides[0].voice
    pictures = [s.src for s in slides]
    sids = [s.id for s in slides]

    spoken = [(p, w) for p, w in zip(paragraphs, windows) if w is not None]
    if not spoken:
        return []

    def named(tag: str) -> str | None:
        for src in pictures:
            name = Path(src).name
            if name == tag or Path(name).stem == tag:
                return src
            if _hint(Path(name).stem)[1] is not None and tag.isdigit():
                if _hint(Path(name).stem)[1] == int(tag):
                    return src
        return None

    cuts: list[SlideCut] = []
    free = list(pictures)
    for i, (para, (a, b)) in enumerate(spoken):
        pick = named(para.picture) if para.picture else None
        if pick is None:
            pick = free[i] if i < len(free) else free[-1]
        cuts.append(SlideCut(
            sid=sids[i] if i < len(sids) else "",
            src=pick, voice=voice_src, tin=a, tout=b,
            note=f"paragraph {i + 1} of {len(spoken)} -- "
                 f"{_opening_words(para.units)}"))

    # More pictures than paragraphs: the ones with nothing of their own
    # share the last paragraph, in equal parts.
    spare = len(pictures) - len(cuts)
    if spare > 0:
        last = cuts[-1]
        share = (last.tout - last.tin) / (spare + 1)
        base_note = last.note
        cuts[-1] = replace(last, tout=round(last.tin + share, 2),
                           note=f"{base_note} (1 of {spare + 1} pictures)")
        for k in range(spare):
            i = len(cuts)
            cuts.append(SlideCut(
                sid=sids[i] if i < len(sids) else "",
                src=pictures[i], voice=voice_src,
                tin=round(last.tin + share * (k + 1), 2),
                tout=round(last.tin + share * (k + 2), 2)
                if k + 2 <= spare else last.tout,
                note=f"{base_note} ({k + 2} of {spare + 1} pictures)"))
    return cuts


def apply_cuts(film, cuts: list["SlideCut"]):
    """The same film with its slides re-cut. Nothing is written.

    `film caption` fits the captions BEFORE it decides whether to write
    anything -- the run without `--apply` is a preview, and a preview
    fitted against the windows the script has just replaced would show
    lines on the wrong pictures and warn about shots that are about to
    change length.
    """
    from .spec import Film

    by_id = {c.sid: c for c in cuts if c.sid}
    shots = []
    for s in film.shots:
        c = by_id.get(s.id)
        if c is None:
            shots.append(s)
            continue
        shots.append(replace(s, src=c.src, voice=c.voice, tin=c.tin,
                             tout=c.tout,
                             duration=(c.tout - c.tin) + VOICE_TAIL,
                             note=c.note or s.note))
    nth = max((int(m.group(1)) for m in
               (re.match(r"^s(\d+)$", s.id) for s in film.shots) if m),
              default=0)
    for c in cuts:
        if c.sid and c.sid in by_id and any(s.id == c.sid for s in film.shots):
            continue
        nth += 1
        shots.append(Shot(src=c.src, kind="still", voice=c.voice, tin=c.tin,
                          tout=c.tout, duration=(c.tout - c.tin) + VOICE_TAIL,
                          move=_EXTRA_SLIDE_MOVE, note=c.note,
                          id=f"s{nth:02d}"))
    return replace(film, shots=shots)


def _opening_words(units: list[str], words: int = 6) -> str:
    """The first few words of a paragraph, for the note on its shot --
    so you can tell at a glance which block of the script a picture is
    holding, without counting paragraphs."""
    said = " ".join(units).split()
    short = " ".join(said[:words])
    return f"'{short}{'...' if len(said) > words else ''}'"


# The keys a slide's own line carries, in the order they are written.
_SLIDE_KEYS = ("src", "voice", "in", "out")


def recut_slides(text: str, cuts: list["SlideCut"]) -> str:
    """Write the re-cut slides into film.yaml AS TEXT.

    Same rule as `add_captions`, for the same reason: comments are not
    data, and `yaml.safe_dump` deletes every one of them -- including
    the header `init` writes explaining what each number means. So each
    shot's block is found by its `- id:` line and only the four lines
    that changed are replaced. The move somebody chose, the focus point
    they clicked, the blank lines and the footer are all left alone.

    A cut with no `sid` is a slide the script asked for and the film
    does not have. It is appended after the last shot -- inside
    `shots:`, before whatever follows it, because nothing outside that
    list is ever read.
    """
    lines = text.splitlines()
    blocks = _shot_blocks(lines)
    by_id = {sid: (at, end, indent) for sid, at, end, indent in blocks}

    drop: set[int] = set()
    inserts: dict[int, list[str]] = {}
    for c in (c for c in cuts if c.sid and c.sid in by_id):
        at, end, dash = by_id[c.sid]
        indent = dash + "  "
        want = {"src": f"{indent}src: {c.src}",
                "voice": f"{indent}voice: {c.voice}",
                "in": f"{indent}in: {tc(c.tin)}",
                "out": f"{indent}out: {tc(c.tout)}"}
        # `duration:` is derived from in/out plus a breath. One left
        # behind from the pause-cut version would pin the picture to the
        # old window while the words moved to the new one.
        seen: set[str] = set()
        for j in range(at + 1, end):
            key = lines[j].strip().split(":")[0]
            if key in want:
                lines[j] = want[key]
                seen.add(key)
            elif key == "duration":
                drop.add(j)
            elif key == "note" and c.note:
                lines[j] = f"{indent}note: {quoted(c.note)}"
                seen.add("note")
        missing = [want[k] for k in _SLIDE_KEYS if k not in seen]
        if c.note and "note" not in seen:
            missing.append(f"{indent}note: {quoted(c.note)}")
        if missing:
            inserts.setdefault(at + 1, []).extend(missing)

    out: list[str] = []
    swapped = False
    for i, line in enumerate(lines):
        if i in inserts:
            out.extend(inserts.pop(i))
        if i in drop:
            continue
        if line in SLIDES_GUESSED:
            if not swapped:
                out.extend(SLIDES_BY_SCRIPT)
                swapped = True
            continue
        out.append(line)

    extra = [c for c in cuts if not c.sid or c.sid not in by_id]
    if extra:
        # After the last shot in the list, never at the end of the file:
        # `shots:` may be followed by a footer, and a block below that is
        # outside the list and is not read at all.
        end = blocks[-1][2] if blocks else len(out)
        while end > 0 and not out[end - 1].strip():
            end -= 1
        dash = blocks[-1][3] if blocks else "  "
        indent = dash + "  "
        nth = _highest_id(blocks)
        block: list[str] = []
        for c in extra:
            nth += 1
            block += ["",
                      f"{dash}- id: s{nth:02d}",
                      f"{indent}src: {c.src}",
                      f"{indent}voice: {c.voice}",
                      f"{indent}in: {tc(c.tin)}",
                      f"{indent}out: {tc(c.tout)}",
                      f"{indent}move: {_EXTRA_SLIDE_MOVE}"]
            if c.note:
                block.append(f"{indent}note: {quoted(c.note)}")
        out[end:end] = block
    return "\n".join(out) + "\n"


# A picture the script asked for that the film had no shot for. `static`
# because there is nothing known about it: the move `init` would have
# chosen came from looking at the picture, and nothing has.
_EXTRA_SLIDE_MOVE = "static"


def _highest_id(blocks) -> int:
    """The largest sNN already in the file, so an added shot never
    collides with one that is there."""
    best = 0
    for sid, *_rest in blocks:
        m = re.match(r"^s(\d+)$", sid)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _shot_blocks(lines: list[str]) -> list[tuple[str, int, int, str]]:
    """(id, first line, one past the last, the dash's indent) for every
    shot in the file.

    A block runs to the next shot, or to the first line at or left of
    the dash's own indent -- which is where `shots:` ends and whatever
    follows it begins. A comment at column 0 counts and has to: `init`
    signs the file off with `# 3 shots, about 16 seconds.`, and treating
    that as part of the last shot put its captions below the footer,
    outside the list, where nothing would read them. An INDENTED comment
    is a note inside the shot and stays in it.
    """
    starts: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", line)
        if m:
            starts.append((i, m.group(2).strip('"\''), m.group(1)))

    out: list[tuple[str, int, int, str]] = []
    for n, (at, sid, dash) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(at + 1, end):
            if not lines[j].strip():
                continue                  # a blank line settles nothing
            if len(lines[j]) - len(lines[j].lstrip()) <= len(dash):
                end = j
                break
        out.append((sid, at, end, dash))
    return out


def add_captions(text: str, by_shot: dict[str, list]) -> str:
    """Write captions into film.yaml AS TEXT, leaving everything else
    exactly as it was found.

    This used to go through yaml.safe_load and yaml.safe_dump, which is
    correct YAML and the wrong thing entirely: comments are not data, so
    every one of them was deleted. And `film go` runs captioning on its
    own -- so the whole explanatory header `build` writes above, the one
    that says what every number means, was gone before anybody had opened
    the file once. Six of the eight films on the machine this was written
    on had no comments left in them at all.

    So: find each shot's block by its `- id:` line, find where that block
    ends, and splice the captions in at the end of it. Nothing else in
    the file is read, parsed or rewritten.

    Appended after any captions already there, which is what the caller
    promises. A shot whose id is not found is skipped rather than guessed
    at.
    """
    lines = text.splitlines()

    # Where each shot's block starts, and how far it is indented.
    starts: list[tuple[int, str, str]] = []      # (line, id, indent)
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", line)
        if m:
            starts.append((i, m.group(2).strip('"\''), m.group(1)))

    inserts: dict[int, list[str]] = {}
    for n, (at, sid, dash_indent) in enumerate(starts):
        caps = by_shot.get(sid)
        if not caps:
            continue
        # The block runs to the next shot, or to the first line at or
        # left of the dash's own indent -- which is where `shots:` ends
        # and whatever follows it begins.
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(at + 1, end):
            stripped = lines[j].strip()
            if not stripped:
                continue                  # a blank line settles nothing
            lead = len(lines[j]) - len(lines[j].lstrip())
            # A comment counts, and has to. `film init` signs the file off
            # with a `# 3 shots, about 16 seconds.` at column 0, and
            # skipping every comment meant the last shot's block ran to
            # the end of the file -- so its captions were written BELOW
            # the footer, outside the shots list, where nothing would read
            # them. An INDENTED comment is a note inside the shot and
            # stays in it.
            if lead <= len(dash_indent):
                end = j
                break
        # A shot's own keys sit one level in from the dash: "  - id:" ->
        # "    src:". Read it off the block rather than assuming two.
        indent = dash_indent + "  "
        for j in range(at + 1, end):
            if lines[j].strip() and not lines[j].strip().startswith("#"):
                indent = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
                break
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1                      # before the blank line, not after

        body = _caption_lines(caps, indent)
        has_captions = any(
            lines[j].strip() == "captions:" for j in range(at + 1, end))
        if has_captions:
            body = body[1:]               # the key is already there
        inserts[end] = body

    captioned = bool(inserts)
    out: list[str] = []
    for i, line in enumerate(lines):
        if i in inserts:
            out.extend(inserts.pop(i))
        if captioned and line in NO_CAPTIONS_YET:
            continue
        out.append(line)
    for rest in inserts.values():         # captions on the very last shot
        out.extend(rest)
    return "\n".join(out) + "\n"


def write(project: Path, force: bool = False, seed: int = 0,
          target: float | None = None) -> Path:
    out = project / "film.yaml"
    if out.exists() and not force:
        raise SystemExit(
            f"{out} already exists. Use --force to overwrite it "
            f"(commit first if you care about it)."
        )
    out.write_text(build(project, seed=seed, target=target), encoding="utf-8")
    return out
