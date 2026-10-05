"""
slides.py  --  the narration cut into slides, and film.yaml changed to match.

Which paragraph of narration.txt belongs to which picture, where each
one is said in the narration, and the surgery on the film.yaml TEXT
that follows: shots recut, captions put in, speed refitted -- always
on the text, so every comment and number a person wrote survives.

Moved out of scaffold.py on 2026-10-05, unchanged: scaffold writes the
first draft; this edits a film that already exists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from . import kinds
from .spec import VOICE_TAIL, Shot

# Moved down to kinds.hint so the timeline can name shots by the same rule.
_hint = kinds.hint


def tc(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f'"{int(m):02d}:{s:05.2f}"'


def narration_of(project: Path) -> Path | None:
    """The film's narration: the newest in media/, never one from
    _discarded/ or _unreadable/ -- a take set aside is not the film's
    soundtrack. The same choice the captions make; see
    kinds.pick_narration."""
    media_dir = project / "media"
    if not media_dir.is_dir():
        return None
    return kinds.pick_narration(
        p for p in media_dir.rglob("*")
        if p.is_file() and not kinds.is_aside(p, media_dir))


# Where the cuts came from, written into the file so that the answer to
# "why is this picture up for thirty seconds" is in the file itself.
# `recut_slides` swaps the first for the second, the way `add_captions`
# takes out NO_CAPTIONS_YET: after a script has said where the paragraphs
# are, a file still claiming the cuts were guessed is simply wrong.
SLIDES_GUESSED = (
    "# Where the cuts go was GUESSED, from where you paused. To say it",
    "# exactly, put your words in narration.txt, one paragraph per picture,",
    "# and run `uv run film caption --apply`.",
)
SLIDES_CUED = (
    "# Cut where you pressed Next while recording, each cut moved to the",
    "# nearest pause so no word is split. To change one, move these",
    "# `in:`/`out:` numbers, or record the narration again.",
)
SLIDES_BY_SCRIPT = (
    "# Cut by the paragraphs of narration.txt -- one paragraph, one picture.",
    "# Change the paragraphs there and run `uv run film caption --apply`",
    "# again, or move these `in:`/`out:` numbers by hand.",
)


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


# A paragraph that is only this is a picture you say nothing over.
NO_WORDS = "-"


def _named(tag: str, pictures: list[str]) -> int | None:
    """The picture a `[3]` or `[3_name.png]` tag names, by position."""
    for j, src in enumerate(pictures):
        name = Path(src).name
        if name == tag or Path(name).stem == tag:
            return j
        num = _hint(Path(name).stem)[1]
        if tag.isdigit() and num is not None and num == int(tag):
            return j
    return None


def _slots(paragraphs, pictures: list[str]) -> list[int]:
    """Which picture each paragraph goes with, as a position -- one past
    the end and beyond when the paragraphs outnumber the pictures. Pure.

    In order, one each. `[5]` jumps to picture 5 and the next paragraph
    carries on from 6: it used to go back to its own position, so after
    one jump the rest were shown over the wrong pictures. `-` on its own
    takes its picture and says nothing over it -- found 2026-09-19,
    eight paragraphs for ten pictures and no way to say which two.
    """
    out, pos = [], 0
    for para in paragraphs:
        tag = getattr(para, "picture", None) if para is not None else None
        j = _named(tag, pictures) if tag else None
        if j is not None:
            pos = j
        out.append(pos)
        pos += 1
    return out


def paragraph_pictures(paragraphs, pictures: list[str]) -> list[str]:
    """The picture for each paragraph. Pure.

    The ONE rule, used by the recording window to decide what to show
    while a paragraph is read, and by `slide_cuts` to decide what to put
    under it afterwards. Two copies of this would sooner or later
    disagree, and the words said over picture 2 would land under
    picture 3 with nothing to say why. The last picture is used again
    when the paragraphs outnumber them.
    """
    return [pictures[min(k, len(pictures) - 1)]
            for k in _slots(paragraphs, pictures)]


def _words(para) -> str:
    text = " ".join(para.units)
    return "" if text.strip() == NO_WORDS else text


def narration_steps(pictures: list[str], paragraphs) -> list[tuple[str, str]]:
    """What the recording window shows, one step at a time: a picture,
    and the words to say over it. Pure.

    Every picture once, in the film's order, with the paragraph(s) that
    go with it (see _slots). A picture with no paragraph of its own is
    shown with no words -- you can still talk about it, and pressing
    Next still marks where. Paragraphs past the last picture are shown
    over it again, one step each. No pictures at all is no steps, and
    the window behaves as it always did.
    """
    if not pictures:
        return []
    texts: list[list[str]] = [[] for _ in pictures]
    extra: list[str] = []
    for para, k in zip(paragraphs, _slots(paragraphs, pictures)):
        (texts[k] if k < len(pictures) else extra).append(_words(para))
    return ([(pic, "\n\n".join(t for t in texts[i] if t))
             for i, pic in enumerate(pictures)]
            + [(pictures[-1], t) for t in extra])


def pictures_in_order(project: Path) -> list[str]:
    """The photographs in media/, in the order `init` will put them in
    the film. As paths relative to the project, the way film.yaml
    writes them.

    ingest's manifest order first where there is one -- it sorts by when
    the shutter fired, and `init` builds from it -- then anything that
    arrived since, alphabetically. Then the filename hints, by the same
    function `build` uses, so a numbered file is where its number says.
    """
    media = project / "media"
    if not media.is_dir():
        return []
    here = [p.relative_to(project).as_posix()
            for p in sorted(media.rglob("*"))
            if p.is_file() and p.suffix.lower() in kinds.STILL
            and not kinds.is_aside(p, media)]
    seen: list[str] = []
    try:
        manifest = json.loads((project / "analysis" / "manifest.json")
                              .read_text(encoding="utf-8"))
        seen = [e["path"] for e in manifest.get("media", [])
                if e.get("path") in here]
    except (OSError, ValueError, KeyError, TypeError):
        seen = []
    seq = seen + [r for r in here if r not in seen]
    tagged = []
    for rel in seq:
        role, num, clean = _hint(Path(rel).stem)
        tagged.append({"entry": {"path": rel}, "role": role, "num": num,
                       "clean": clean})
    return [t["entry"]["path"] for t in _in_film_order(tagged)[0]]


_TAKEN_AT = re.compile(r"(\d{8})-(\d{4,6})")


def _taken_at(name: str) -> str | None:
    """The time in a take's name, as text that sorts: `rec_20260919-1224`
    and `voiceover_20260919-130000` both carry one (record.take_name).
    The name, not the file's time -- copying a file can change that."""
    m = _TAKEN_AT.search(name)
    return m and m.group(1) + m.group(2).ljust(6, "0")


def place_takes(ordered: list[dict], narration: str | None) -> list[dict]:
    """A take said to the camera before the narration goes just before
    the pictures; one said after it, just after them. Pure.

    Found 2026-09-19: an intro recorded first, then photos numbered 1_ to
    10_ talked over -- and the numbers put every photo ahead of the
    unnumbered intro, so the film opened on the slides and ended on
    "hello". The order you recorded in is the order you meant. A take
    you numbered yourself stays where you numbered it.
    """
    when = narration and _taken_at(narration)
    if not when:
        return ordered

    def stem(t):
        return Path(t["entry"]["path"]).stem

    # A take named open_/close_ is already placed by its name.
    takes = [t for t in ordered if t["num"] is None and not t.get("role")
             and kinds.is_recording(stem(t)) and _taken_at(stem(t))]
    if not takes:
        return ordered
    rest = [t for t in ordered if not any(t is k for k in takes)]
    # First appearances only: an open_close card plays again at the very
    # end, and a closing word belongs before it, not after the film's
    # last frame.
    pics = [i for i, t in enumerate(rest)
            if Path(t["entry"]["path"]).suffix.lower()
            in kinds.STILL | kinds.HEIC
            and not any(t is u for u in rest[:i])]
    if not pics:
        return ordered
    lo, hi = pics[0], pics[-1] + 1
    before = [t for t in takes if _taken_at(stem(t)) < when]
    after = [t for t in takes if _taken_at(stem(t)) >= when]
    return rest[:lo] + before + rest[lo:hi] + after + rest[hi:]


def _in_film_order(tagged: list[dict], repeat_open_close: bool = False):
    """Numbered first by number, then openers, the rest, closers.

    Returns (ordered, numbered, middle): `build` needs the last two to
    decide whether a quote card's place was a guess.
    """
    numbered = sorted((t for t in tagged if t["num"] is not None),
                      key=lambda t: t["num"])
    unnumbered = [t for t in tagged if t["num"] is None]
    openers = [t for t in unnumbered if t["role"] in ("open", "open_close")]
    closers = [t for t in unnumbered if t["role"] == "close"]
    middle = [t for t in unnumbered if t["role"] not in
              ("open", "close", "open_close")]
    ordered = numbered + openers + middle + closers
    if repeat_open_close:
        # open_close: the SAME file also plays at the very end -- true
        # whether it got there by role (unnumbered) or by an explicit
        # number.
        for t in unnumbered + numbered:
            if t["role"] == "open_close":
                ordered.append(t)
    return ordered, numbered, middle


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

    spoken = [(p, w, pic) for p, w, pic in
              zip(paragraphs, windows, paragraph_pictures(paragraphs,
                                                          pictures))
              if w is not None]
    if not spoken:
        return []

    cuts: list[SlideCut] = []
    for i, (para, (a, b), pick) in enumerate(spoken):
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


def refit_speed(text: str, film, speed: float) -> str:
    """film.yaml AS TEXT with every sped-up shot moved to `speed`, and
    its captions moved with it. For `film fit`.

    A caption's `at`, `dur` and `words` are in FILM seconds, already
    divided by the shot's speed when `film caption` wrote them. Changing
    only `speed:` moves the voice and leaves the captions behind (about
    0.9 s late, 28 s into a shot, at 1.2 -> 1.24). Going from speed a to b
    multiplies every film time inside the shot by a / b: exact, and no
    new transcription.

    Only shots that already have a `speed` other than 1.0 are touched
    (the takes and the narrated pictures), and nothing else in the file
    is read or rewritten, so comments and notes survive. A shot whose
    captions are not written the way `film caption` writes them -- one
    `at:`, `dur:` and `words:` per line -- raises ValueError instead of
    being guessed at.
    """
    lines = text.splitlines()
    shots = {s.id: s for s in film.shots}
    for sid, first, end, _dash in _shot_blocks(lines):
        shot = shots.get(sid)
        if shot is None or abs(shot.speed - 1.0) < 1e-3:
            continue
        k = shot.speed / speed
        found = {"at": 0, "dur": 0, "words": 0}
        for i in range(first + 1, end):
            line = lines[i]
            m = re.match(r"^(\s*speed:\s*)[0-9.]+(.*)$", line)
            if m:
                lines[i] = f"{m.group(1)}{speed:g}{m.group(2)}"
                continue
            m = re.match(r"^(\s+(?:at|dur):\s*)([0-9.]+)\s*$", line)
            if m:
                key = "at" if "at:" in m.group(1) else "dur"
                found[key] += 1
                lines[i] = f"{m.group(1)}{float(m.group(2)) * k:.2f}"
                continue
            m = re.match(r"^(\s+words:\s*)\[(.*)\]\s*$", line)
            if m:
                found["words"] += 1
                nums = [float(x) * k for x in m.group(2).split(",") if x.strip()]
                lines[i] = (m.group(1) + "["
                            + ", ".join(f"{n:.2f}" for n in nums) + "]")
        want = len(shot.captions)
        if (found["at"], found["dur"]) != (want, want) or \
                found["words"] != sum(1 for c in shot.captions if c.words):
            raise ValueError(
                f"shot {sid}: its captions are not written one value per "
                f"line, so their times cannot be moved safely.")
    return "\n".join(lines) + "\n"


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
