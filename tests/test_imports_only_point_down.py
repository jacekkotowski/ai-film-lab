"""
The layers of ffilm, and the rule that keeps them layers.

A module may import only from a LOWER layer. Foundations know nothing
about stages, stages know nothing about the ways in. That is what lets a
reader understand spec.py without reading cli.py, and what lets a change
to the command line never break the renderer.

Today's violations are listed in KNOWN_EXCEPTIONS, each with the reason.
The list may only shrink: a new violation fails, and so does an entry
that has been fixed but not removed. The day it is empty, the package can
be split into folders along these lines without a single surprise.

Reads the source with `ast` -- nothing is imported, nothing runs.
"""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "ffilm"

LAYERS = {
    # 0  foundations: no ffilm imports at all
    "__init__": 0, "kinds": 0, "pix": 0, "paths": 0, "ffmpeg": 0,
    "fonts": 0, "history": 0, "pack": 0,
    # 1  the shared shelf
    "library": 1,
    # 2  what a film IS
    "spec": 2,
    # 3  the movement vocabulary
    "moves": 3,
    # 4  getting and reading the material
    "record": 4, "ingest": 4,
    # 5  sound and words, built from the analysis
    "audio": 5, "voice": 5, "cover": 5,
    # 6  pixels, and captions fitted to shots
    "render": 6, "caption_fit": 6,
    # 7  workflows built on all of that
    "scaffold": 7, "booth": 7, "checks": 7,
    # 8  the ways in
    "guide": 8, "editor": 8,
    # 9  the command line, which dispatches to everything
    "cli": 9,
}

# Every upward import that is still true, with the reason. Empty since
# 2026-09-13 -- keep it that way: move the shared piece down instead.
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {}


def ffilm_imports(path: Path) -> set[str]:
    """Every ffilm module this file imports, including inside functions."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level >= 1 and node.module:          # from .spec import X
                found.add(node.module.split(".")[0])
            elif node.level >= 1:                         # from . import spec
                found.update(a.name for a in node.names)
            elif node.module and node.module.startswith("ffilm."):
                found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("ffilm."):
                    found.add(a.name.split(".")[1])
    return found


def all_edges() -> set[tuple[str, str]]:
    return {(p.stem, target)
            for p in PKG.glob("*.py")
            for target in ffilm_imports(p) if target != p.stem}


def upward_edges() -> set[tuple[str, str]]:
    return {(a, b) for a, b in all_edges()
            if a in LAYERS and b in LAYERS and LAYERS[b] >= LAYERS[a]}


def test_every_module_has_a_place_in_the_layers():
    missing = sorted(p.stem for p in PKG.glob("*.py") if p.stem not in LAYERS)
    assert not missing, (
        f"New module(s) {missing}: add each to LAYERS in this file, at the "
        f"lowest layer whose imports it satisfies.")


def test_imports_only_point_down():
    new = sorted(upward_edges() - KNOWN_EXCEPTIONS.keys())
    assert not new, "\n".join(
        f"{a} (layer {LAYERS[a]}) imports {b} (layer {LAYERS[b]}): move the "
        f"shared piece down a layer instead" for a, b in new)


def test_the_list_of_exceptions_only_shrinks():
    fixed = sorted(KNOWN_EXCEPTIONS.keys() - upward_edges())
    assert not fixed, (
        f"No longer true, remove from KNOWN_EXCEPTIONS: {fixed}")
