"""
retakes.py  --  one picture's words said again, put into the film.

`film record --voice --picture N` records one paragraph; this finds the
words in that take and changes only the shot it belongs to.

Moved out of scaffold.py on 2026-10-05, unchanged.
"""

from __future__ import annotations

from pathlib import Path

from . import kinds
from .slides import (SlideCut, _shot_blocks, add_captions, narration_of,
                     narration_steps, pictures_in_order, recut_slides)
from .spec import Shot


# --------------------------------------------------------------------------
# One picture's words, said again (`film record --voice --picture N`)
# --------------------------------------------------------------------------
# Asked for 2026-09-23: Turn Heat Into Images took 10 narration takes in
# one morning, about 3 minutes each, because a fluffed sentence over one
# picture meant reading all six again. A shot already names its own
# sound file, so a retake only has to change what one shot points at.

# Kept around the words: the breath before them and the reach for SPACE
# after them are not the picture's words, but cutting on the word itself
# clips its first consonant.
RETAKE_PAD = 0.3


def picture_shots(film) -> list:
    """The photographs of the film, in film order. Picture N is the Nth
    of these, the same count the notes use ("picture 4 of 6"), so a
    talking head before the pictures is not picture 1.

    A photograph from media/ counts with or without words yet (found
    2026-10-02, Excel Time Logic: pictures 6 and 7 were never narrated
    and `--picture 6` was out of range, so the only way to give them a
    voice was to read all seven again). The opening card, which lives in
    analysis/, is not a picture."""
    return [s for s in film.shots if s.kind == "still"
            and (s.voice or s.src.replace("\\", "/").startswith("media/"))]


def retake_cut(film, n: int, voice_rel: str, tin: float,
               tout: float) -> SlideCut | None:
    """Picture n pointed at a new take, or None if the film has no
    picture n. Everything else about the shot is left as it is."""
    shots = picture_shots(film)
    if not 1 <= n <= len(shots):
        return None
    s = shots[n - 1]
    return SlideCut(sid=s.id, src=s.src, voice=voice_rel,
                    tin=round(tin, 2), tout=round(tout, 2),
                    note=f"picture {n} of {len(shots)} -- said again, "
                         f"{Path(voice_rel).name}")


def speech_window(lines, length: float) -> tuple[float, float]:
    """From just before the first word to just after the last. The
    whole take when nothing was heard."""
    if not lines:
        return 0.0, round(length, 2)
    a = max(0.0, min(ln.start for ln in lines) - RETAKE_PAD)
    b = min(length, max(ln.end for ln in lines) + RETAKE_PAD)
    return round(a, 2), round(b, 2)


def drop_captions(text: str, sid: str) -> str:
    """This shot's `captions:` and everything under it, taken out AS
    TEXT -- the rest of the file stays exactly as it was (see
    add_captions for why never through yaml.safe_dump)."""
    lines = text.splitlines()
    for bid, at, end, _dash in _shot_blocks(lines):
        if bid != sid:
            continue
        for j in range(at + 1, end):
            if lines[j].strip() == "captions:":
                key = len(lines[j]) - len(lines[j].lstrip())

                def under(line: str) -> bool:
                    """Blank, deeper than `captions:`, or a list item at
                    its own depth -- YAML allows both."""
                    lead = len(line) - len(line.lstrip())
                    return (not line.strip() or lead > key
                            or (lead == key and line.lstrip().startswith("-")))
                k = j + 1
                while k < end and under(lines[k]):
                    k += 1
                while k > j + 1 and not lines[k - 1].strip():
                    k -= 1                # the blank line before the next shot stays
                del lines[j:k]
                break
        break
    return "\n".join(lines) + "\n"


def retake_text(text: str, cut: SlideCut, captions: list) -> str:
    """film.yaml with one picture pointed at its new take and given the
    new take's captions. Its old captions go: they were timed to the old
    reading."""
    text = recut_slides(text, [cut])
    text = drop_captions(text, cut.sid)
    return add_captions(text, {cut.sid: captions}) if captions else text


def latest_retakes(found, since: float) -> dict[str, str]:
    """{picture: retake} -- the newest retake of each picture recorded
    after the narration. Pure: `found` is (retake, picture, time).
    One from before the narration was read over again by it."""
    best: dict[str, tuple[float, str]] = {}
    for rel, picture, when in found:
        if when > since and (picture not in best or when > best[picture][0]):
            best[picture] = (when, rel)
    return {p: rel for p, (_w, rel) in best.items()}


def keep_retakes(project: Path, text: str) -> str:
    """A rewritten edit keeps the pictures said again since the
    narration. `init --force` / `go --rewrite` cut every picture from the
    narration, and would quietly put the fluffed reading back."""
    from .record import read_retake
    narration = narration_of(project)
    media = project / "media"
    if narration is None or not media.is_dir():
        return text
    found = []
    for p in media.iterdir():
        if p.is_file() and kinds.is_picture_retake(p):
            r = read_retake(p)
            if r:
                found.append((p.relative_to(project).as_posix(),
                              r["picture"], p.stat().st_mtime))
    keep = latest_retakes(found, narration.stat().st_mtime)
    if not keep:
        return text
    # Read, not Film.load: that checks every file exists, and this text
    # is not film.yaml yet.
    import yaml
    from types import SimpleNamespace
    raw = (yaml.safe_load(text) or {}).get("shots") or []
    film = SimpleNamespace(shots=[Shot.parse(d, i) for i, d in
                                  enumerate(raw)])
    for n, s in enumerate(picture_shots(film), 1):
        rel = keep.get(s.src)
        if rel:
            r = read_retake(project / rel)
            text = recut_slides(text, [retake_cut(film, n, rel, r["in"],
                                                  r["out"])])
    return text


def picture_menu(film) -> list[str]:
    """One line per picture that has words over it, numbered the way
    `--picture N` counts, with the first words said -- so the number is
    picked by what was said, not by counting."""
    out = []
    for n, s in enumerate(picture_shots(film), 1):
        first = s.captions[0].text if s.captions else ""
        out.append(f"{n:>3}  {Path(s.src).name}"
                   + (f"  '{first[:40]}{'...' if len(first) > 40 else ''}'"
                      if first else ""))
    return out


def words_for_picture(project: Path, film, n: int, script: str) -> str:
    """What to show in the window over picture n: its paragraph of
    narration.txt, or else the captions it has -- they are what was
    said."""
    from .voice import script_paragraphs
    shot = picture_shots(film)[n - 1]
    for rel, text in narration_steps(pictures_in_order(project),
                                     script_paragraphs(script or "")):
        if rel == shot.src and text.strip():
            return text
    return "\n".join(c.text for c in shot.captions)


def retake_picture(project: Path, n: int, take: Path, words: str,
                   model: str = "small") -> list[str]:
    """Point picture n at a take just recorded, with its own captions.
    Returns what to tell the person. film.yaml is put back as it was if
    the result would not load.

    Older retakes of the same picture go to media/_discarded/: they are
    what this one replaces."""
    from . import caption_fit, ingest, record, voice
    from .spec import Film

    yml = project / "film.yaml"
    film = Film.load(yml, check_files=False)
    shot = picture_shots(film)[n - 1]
    rel = take.relative_to(project).as_posix()
    length = record.verify_take(take, None, False)[0]

    said: list[str] = []
    try:
        lines = voice.transcribe(take, model_size=model, script=words or None)
    except SystemExit as e:             # the voice extra is not installed
        lines = []
        said.append(f"No captions for it: {e}")
    tin, tout = speech_window(lines, length)
    record.write_retake(take, shot.src, tin, tout, words)

    media = project / "media"
    for p in media.iterdir():
        r = (record.read_retake(p) if p.is_file() and p != take
             and kinds.is_picture_retake(p) else None)
        if r and r["picture"] == shot.src:
            for f in (p, p.with_name(p.stem + record.RETAKE_SUFFIX)):
                if f.exists():
                    ingest.quarantine(f, media, where=kinds.DISCARDED_DIRNAME)
            said.append(f"The earlier retake {p.name} -> "
                        f"{kinds.DISCARDED_DIRNAME}\\")

    before = yml.read_text(encoding="utf-8")
    cut = retake_cut(film, n, rel, tin, tout)
    yml.write_text(retake_text(before, cut, []), encoding="utf-8")
    try:
        placed, _ = caption_fit.fit_lines_to_shots(
            Film.load(yml, check_files=False),
            voice.VoiceSource(take, take.name, [rel]), lines)
        caps = placed.get(shot.id, [])
        if caps:
            yml.write_text(add_captions(yml.read_text(encoding="utf-8"),
                                        {shot.id: caps}), encoding="utf-8")
        Film.load(yml, check_files=False)
    except SystemExit as e:
        yml.write_text(before, encoding="utf-8")
        raise SystemExit(f"film.yaml was put back as it was: {e}")

    old = (shot.tout or 0) - shot.tin
    return [f"Picture {n} ({Path(shot.src).name}) now has {take.name}: "
            f"{tout - tin:.1f}s of words (was {old:.1f}s), "
            f"{len(caps)} caption(s).",
            "No other shot changed."] + said
