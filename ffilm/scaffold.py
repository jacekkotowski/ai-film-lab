"""
scaffold.py  --  write a first film.yaml from what ingest found.

Deliberately not clever. It gives you a complete, valid, watchable film
in one command, so your first render never depends on anyone else. Then
you change the numbers -- which is the whole point of the system.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import kinds
from .moves import choose_moves
from .record import REC_SPEED, is_recording
from .spec import Caption, Shot, pretty_name


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
QUOTE_SECONDS = 5.0          # a quote needs to be READ, not glanced at

# Filename hints, checked so you can drop files in fast without opening
# film.yaml at all. None of these are required -- unhinted files just
# fall back to plain alphabetical order.
#
#   00_thing.jpg, 01_thing.jpg    explicit numbered order (checked first)
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
_NUM_PREFIX = re.compile(r"^(\d{1,3})[_.\-\s]+")


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

    audio = next((p for p in sorted((project / "media").rglob("*"))
                  if p.suffix.lower() in AUDIO_EXT), None)

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

    shots: list[Shot] = []
    meta: list[dict] = []
    for t in ordered:
        e, role, clean = t["entry"], t["role"], t["clean"]
        if e["kind"] == "still":
            if role in ("open", "close", "open_close"):
                dur = OPENER_CLOSER_SECONDS
                mv = "static"
            elif role == "quote":
                dur = QUOTE_SECONDS
                mv = "static"
            else:
                dur = FACE_SECONDS if e.get("focus_from") == "face" else STILL_SECONDS
                mv = "auto"
            s = Shot(src=e["path"], kind="still", duration=dur, move=mv,
                     focus=tuple(e.get("focus", (0.5, 0.5))),
                     id=f"s{len(shots) + 1:02d}")
            if role == "quote":
                s.captions.append(Caption(text=_title_from_stem(clean), at=0.3,
                                          dur=max(1.0, dur - 0.6), pos="center"))
            shots.append(s)
            meta.append({"entry": e, "role": role})
        else:
            segments = video_segments(e)
            talking = is_talking(e)
            spd = _speed_for(e["path"])
            spot = _video_focus(e)
            for k, (a, b) in enumerate(segments, 1):
                s = Shot(src=e["path"], kind="video", duration=(b - a) / spd,
                         tin=a, tout=b, speed=spd,
                         move=(TALKING_MOVES[(len(shots)) % len(TALKING_MOVES)]
                               if talking else "auto"),
                         amount=TALKING_AMOUNT if talking else 1.0,
                         focus=spot,
                         id=f"s{len(shots) + 1:02d}",
                         # Only where a pause was cut out of one take. A
                         # hard cut on the same face a second later reads
                         # as a stumble; everywhere else, cuts are right.
                         dissolve=DISSOLVE if (talking and k > 1) else 0.0)
                shots.append(s)
                meta.append({"entry": e, "in": a, "out": b, "role": role,
                             "talking": talking, "part": k,
                             "parts": len(segments)})

    if not shots:
        raise SystemExit("No usable media found. Is anything in media/ ?")

    target_notes: list[str] = []
    if target:
        target_notes = fit_to_target(shots, meta, float(target))
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
    if audio:
        L.append(f'audio: {audio.relative_to(project).as_posix()}')
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
    L.append("shots:")
    L.extend(title_card_block(project, vertical))

    for s, m in zip(shots, meta):
        L.extend(shot_block(s, m))

    L.append("")
    total = sum(s.duration for s in shots)
    L.append(f"# {len(shots)} shots, about {total:.0f} seconds.")
    for note in target_notes:
        L.append(note)
    if ambiguous_quotes:
        L.append("#")
        L.append("# NOTE: a quote_ card was placed by guesswork among other")
        L.append("# unnumbered files -- its position (before/after other shots)")
        L.append("# was NOT something the filename could tell me. Check the")
        L.append("# order above; if it's wrong, either reorder the shots: blocks")
        L.append("# below, or rename files 00_, 01_, 02_... and run init again.")
    if not any(m.get("role") == "quote" for m in meta):
        L.append("# Speech captions are left out on purpose -- run")
        L.append("# `uv run film caption` once you're happy with the shots,")
        L.append("# or watch it once and add what actually needs saying.")
    L.append("")
    return "\n".join(L)


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
        f"    duration: {TITLE_CARD_SECONDS:.1f}",
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
    elif m.get("talking"):
        if m["parts"] > 1:
            note = (f"part {m['part']} of {m['parts']} -- one take with "
                    f"the long pauses cut out. Every word is kept")
        else:
            note = ("kept whole -- there is sound on this one, so none "
                    "of what you said is cut. Trim in:/out: if it drags")
        L.append(f"    note: {json.dumps(note)}")
    elif e.get("focus_from") == "face":
        L.append("    note: \"face detected -- given longer screen time\"")
    elif e.get("from"):
        L.append(f"    note: {json.dumps('converted from ' + Path(e['from']).name)}")
    if s.captions:
        L.append("    captions:")
        for c in s.captions:
            L.append(f"      - text: {json.dumps(c.text)}")
            L.append(f"        at: {c.at}")
            L.append(f"        dur: {c.dur}")
            L.append(f"        pos: {c.pos}")
    return L


MIN_SHOT = 2.0               # no still is worth less screen time than this


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


def shots_for(entry: dict, first_id: int) -> tuple[list[Shot], list[dict]]:
    """The shot(s) one media file becomes. Shared by writing a film from
    scratch and adding to one that already exists."""
    shots, meta = [], []
    stem = Path(entry["path"]).stem
    role, _num, clean = _hint(stem)

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
            shots.append(Shot(src=entry["path"], kind="video",
                              duration=(b - a) / spd,
                              tin=a, tout=b, speed=spd,
                              move=(TALKING_MOVES[len(shots) % len(TALKING_MOVES)]
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
        s, m = shots_for(e, next_id + len(shots))
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
