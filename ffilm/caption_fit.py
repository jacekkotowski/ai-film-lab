"""
caption_fit.py  --  place transcript lines onto the shots they were said over.

Two cases, because there are two kinds of source audio:

Global track (a `voiceover.*` file, or any standalone audio file) plays
under the whole film from the start. Its timeline and the film's overall
timeline are the same clock, so placing a line is just: which shot
covers this moment in the finished film?

Per-clip track (audio pulled out of one of your .mp4 clips) has its own
clock -- the clip's OWN original timeline, before you trimmed it with
`in:`/`out:`. A line at 0:42 in the source video only matters to shots
that (a) use that exact clip and (b) whose `in:`/`out:` window actually
contains 0:42. Everything else in the film is irrelevant to that line.
"""

from __future__ import annotations

from dataclasses import replace

from .spec import Caption, Film
from .voice import Line, VoiceSource

MAX_CAPTION_SECONDS = 4.5   # a caption held longer than this is hard to read


def _place(sid: str, s0: float, s1: float, ln: Line,
          warnings: list[str], speed: float = 1.0) -> Caption | None:
    """Shared clamp-and-warn logic for one line landing on one shot,
    given that shot's start/end on WHATEVER clock the line uses.

    `speed` converts that clock to the film's. A shot at speed 1.2 plays
    its source 20% faster, so a line heard 6s into the take belongs on
    screen at 5s, and is held for 20% less time once it is there.
    Without this, every caption on a sped-up shot appeared late -- and
    progressively later the further into the shot it was.
    """
    shot_len = (s1 - s0) / speed
    # Rounded BEFORE the clamp, not after. Rounding `at` up and `dur`
    # down independently is how a caption that fitted by construction
    # came out six hundredths of a second too long in the file -- and
    # the film then refused to load.
    at = round(max(0.0, (ln.start - s0) / speed), 2)
    line_dur = ln.dur / speed
    room = shot_len - at
    if room < 0.4:
        warnings.append(f'[{sid}] dropped, no room left: "{ln.text}"')
        return None
    dur = min(line_dur, MAX_CAPTION_SECONDS, room)
    # Only worth mentioning when the SHOT ran out. Being clipped at
    # MAX_CAPTION_SECONDS is the design -- a line held longer than four
    # and a half seconds is just sitting there -- and warning about it
    # sent people off lengthening shots that were the right length.
    if dur < line_dur - 0.05 and room < min(line_dur, MAX_CAPTION_SECONDS):
        warnings.append(f'[{sid}] cut short, the shot ends first: "{ln.text}"')
    # Rounded DOWN, so the written numbers can never add up to more than
    # the shot they sit on.
    dur = int(dur * 100) / 100.0
    # On the caption's own clock, at the shot's speed -- the same
    # conversion `at` just had, for the same reason.
    words = [round((w - ln.start) / speed, 2) for w in ln.words
             if (w - ln.start) / speed < dur]
    return Caption(text=ln.text, at=at, dur=dur, pos="lower_third",
                   words=words)


def stop_overlap(caps: list[Caption], sid: str,
                 warnings: list[str]) -> list[Caption]:
    """No two captions in the same place on screen at the same time.

    `_place` sizes each line on its own and never looks at the next one,
    so a line that ran long -- or, far more often, one that MAX_CAPTION_
    SECONDS clipped to 4.5s -- sat there at full opacity while the next
    one faded in underneath it. Rendered as two sentences printed over
    each other, unreadable, and it survived every render because nothing
    downstream is in a position to notice.

    Measured on a real film: 81 frames of it, from two captions.

    A caption is shortened to end exactly where the next one begins, so
    what is left is a proper crossfade -- the outgoing one fading out
    over its own `fade` while the incoming one fades in. Shortened, never
    dropped: the words were said, and the shot is where they were said.

    Only captions sharing a `pos` can collide; the whole point of `pos`
    is that two lines in different places are two lines in different
    places.
    """
    out: list[Caption] = []
    for pos in {c.pos for c in caps}:
        same = sorted([c for c in caps if c.pos == pos], key=lambda c: c.at)
        for cap, nxt in zip(same, same[1:]):
            if cap.at + cap.dur > nxt.at + 1e-6:
                # Rounded DOWN, for the reason _place rounds down: the
                # numbers written into film.yaml may never add up to more
                # than the room they were given.
                cut = int(max(0.0, nxt.at - cap.at) * 100) / 100.0
                warnings.append(
                    f'[{sid}] shortened to {cut:.2f}s, the next caption '
                    f'starts: "{cap.text}"')
                cap = replace(cap, dur=cut)
            out.append(cap)
        if same:
            out.append(same[-1])
    return sorted(out, key=lambda c: c.at)


def fit_global(film: Film, lines: list[Line]) -> tuple[dict[str, list[Caption]], list[str]]:
    """A track that plays under the whole film -- match by position in
    the finished film's own timeline."""
    warnings: list[str] = []
    bounds = []
    t = 0.0
    for s in film.shots:
        bounds.append((s.id, t, t + s.duration))
        t += s.duration

    out: dict[str, list[Caption]] = {sid: [] for sid, _, _ in bounds}
    for ln in lines:
        best_id, best_overlap = None, 0.0
        best_bounds = None
        for sid, s0, s1 in bounds:
            overlap = min(ln.end, s1) - max(ln.start, s0)
            if overlap > best_overlap:
                best_overlap, best_id, best_bounds = overlap, sid, (s0, s1)
        if best_id is None:
            continue
        cap = _place(best_id, *best_bounds, ln, warnings)
        if cap:
            out[best_id].append(cap)
    out = {k: stop_overlap(v, k, warnings) for k, v in out.items() if v}
    return out, warnings


def fit_per_clip(film: Film, source: VoiceSource,
                 lines: list[Line]) -> tuple[dict[str, list[Caption]], list[str]]:
    """A track extracted from one specific video clip -- match by the
    CLIP's own original timeline, restricted to shots that use it."""
    warnings: list[str] = []
    shots = [s for s in film.shots if s.src in source.shot_srcs]
    if not shots:
        return {}, [f'no shot in film.yaml uses {source.label}']

    out: dict[str, list[Caption]] = {s.id: [] for s in shots}
    for ln in lines:
        best_id, best_overlap = None, 0.0
        best_bounds = None
        best_speed = 1.0
        for s in shots:
            s0 = s.tin
            s1 = s.tin + s.duration * s.speed
            overlap = min(ln.end, s1) - max(ln.start, s0)
            if overlap > best_overlap:
                best_overlap, best_id, best_bounds = overlap, s.id, (s0, s1)
                best_speed = s.speed
        if best_id is None:
            continue
        cap = _place(best_id, *best_bounds, ln, warnings, best_speed)
        if cap:
            out[best_id].append(cap)
    out = {k: stop_overlap(v, k, warnings) for k, v in out.items() if v}
    return out, warnings


def fit_lines_to_shots(film: Film, source: VoiceSource,
                       lines: list[Line]) -> tuple[dict[str, list[Caption]], list[str]]:
    """Dispatch to the right matching strategy for this source."""
    if source.shot_srcs:
        return fit_per_clip(film, source, lines)
    return fit_global(film, lines)
