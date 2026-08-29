"""
pack.py  --  a zip you can carry to another computer.

Almost nothing here is clever, and that is the point. The toolkit is
about 1.4 MB of text; everything heavy is either regenerable or is your
own footage. So a portable copy is: the text, your originals if you ask
for them, and a SETUP.bat that installs the two programs Windows does
not come with.

What it deliberately leaves out, and why:

  .venv/        388 MB of absolute paths baked in at build time. Useless
                on any other machine; `uv sync` rebuilds it in a minute.
  out/          every render you have ever made. The largest thing in the
                folder by far, and all of it comes back from film.yaml.
  analysis/     proxies and thumbnails. `film ingest` rebuilds them.
  .devices.json which camera THIS laptop has. The next one has another.
  .git/         history, kept out of a handoff on purpose -- see below.

Not an offline installer. It does not vendor wheels or ship ffmpeg.exe:
that would be half a gigabyte, locked to one Windows and one Python, and
it would rot quietly until the day you needed it. Two winget lines are
better than a bundle that expires.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

# The toolkit itself. Listed rather than globbed, so that something new
# and enormous appearing at the top level never silently doubles the
# size of everybody's zip.
TOOLKIT = [
    # The shelf travels with the toolkit, not with any one film: it is
    # not big, and a copy that arrives without the music is a copy where
    # every film has quietly lost its soundtrack.
    "library",
    "ffilm", "tests", "blender", "data",
    "pyproject.toml", "uv.lock", "CLAUDE.md", "README.md",
    "HOW_TO_USE.md", "FILM.bat", ".gitignore", ".gitattributes",
    "_fetch.py",
]

# Of a project, the parts that cannot be made again.
PROJECT_KEEP = ["media", "music", "cover", "film.yaml", "script.txt",
                ".vertical"]

SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", ".Rproj.user",
             ".idea", ".vscode", "out", "analysis", "proxies", "thumbs"}
SKIP_NAMES = {".devices.json", ".lastfilm", "last_error.txt",
              "film.yaml.bak", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = {".pyc", ".pyo", ".zip"}


def wanted(rel: Path) -> bool:
    """Should this path, relative to the toolkit root, travel?"""
    parts = rel.parts
    if any(p in SKIP_DIRS for p in parts):
        return False
    if rel.name in SKIP_NAMES:
        return False
    return rel.suffix.lower() not in SKIP_SUFFIX


def _walk(base: Path, root: Path) -> list[Path]:
    if not base.exists():
        return []                    # an optional part, simply not here
    if base.is_file():
        return [base] if wanted(base.relative_to(root)) else []
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and wanted(p.relative_to(root)):
            out.append(p)
    return out


def contents(root: Path, projects: list[str] | None = None
             ) -> list[tuple[Path, str]]:
    """Every file that goes in, as (real path, name inside the zip)."""
    found: list[tuple[Path, str]] = []
    for name in TOOLKIT:
        for p in _walk(root / name, root):
            found.append((p, p.relative_to(root).as_posix()))

    for proj in projects or []:
        base = root / "projects" / proj
        if not base.is_dir():
            raise SystemExit(f"No project called {proj!r} to pack.")
        for keep in PROJECT_KEEP:
            for p in _walk(base / keep, root):
                found.append((p, p.relative_to(root).as_posix()))
    return found


SETUP_BAT = r"""@echo off
REM ============================================================
REM  SETUP  --  run me once, on a computer that has never had this.
REM  Everything after this is FILM.bat.
REM ============================================================
cd /d "%~dp0"
echo.

where uv >nul 2>&1
if errorlevel 1 (
  echo Installing uv ...
  winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
  echo.
  echo   uv is installed, but this window cannot see it yet.
  echo   CLOSE this window, open the folder again, and run SETUP again.
  echo.
  pause
  exit /b
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo Installing ffmpeg ...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  echo.
  echo   ffmpeg is installed, but this window cannot see it yet.
  echo   CLOSE this window, open the folder again, and run SETUP again.
  echo.
  pause
  exit /b
)

echo Fetching the four packages the film needs ...
uv sync
if errorlevel 1 goto failed

REM A git repository here is what gives you an undo: every render
REM commits film.yaml, so an edit you regret is always recoverable.
REM Skipped in silence if git is not installed -- nothing depends on it.
where git >nul 2>&1
if not errorlevel 1 (
  if not exist ".git" (
    git init -q
    git add -A >nul 2>&1
    git -c user.name="film" -c user.email="film@localhost" commit -q -m "arrived on this computer" >nul 2>&1
  )
)

echo.
echo   Ready. Double-click FILM.bat.
echo.
pause
exit /b

:failed
echo.
echo   That did not finish. The usual cause is no internet, or a
echo   company laptop blocking winget. HOW_TO_USE.md, Part 1, has
echo   the manual version.
echo.
pause
"""


READ_ME_FIRST = """AI FILM LAB -- on a new computer

1. Double-click SETUP.bat. It installs the two programs Windows does not
   come with (uv and ffmpeg) and fetches the four packages the film
   needs. It may tell you to close the window and run it again -- that is
   normal, and it only happens once.

2. Double-click FILM.bat. That is the whole thing from then on.

HOW_TO_USE.md is the long version if anything goes sideways.

What is NOT in this zip, on purpose:

  the renders (out/)        they come back from film.yaml
  the analysis (analysis/)  `film ingest` rebuilds it
  the installed packages    `uv sync` fetches them, matched exactly to
                            uv.lock so this computer behaves like the
                            one the zip came from

If a project came along, its originals are in projects/<name>/media and
are the one thing here that cannot be made again. Back those up the way
you back up photographs.
"""


def build(root: Path, out: Path, projects: list[str] | None = None) -> int:
    """Write the zip. Returns its size in bytes."""
    files = contents(root, projects)
    top = out.stem
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for real, arc in files:
            z.write(real, f"{top}/{arc}")
        z.writestr(f"{top}/SETUP.bat", SETUP_BAT)
        z.writestr(f"{top}/READ_ME_FIRST.txt", READ_ME_FIRST)
    return out.stat().st_size


def default_name(projects: list[str] | None) -> str:
    stem = "AI-Film"
    if projects:
        stem += "-" + "-".join(projects)
    return f"{stem}-{date.today().isoformat()}.zip"
