"""
history.py  --  a quiet undo for film.yaml.

Every render commits the film.yaml it is about to render, if it changed
since the last one. That is the whole feature. It exists because the loop
this toolkit is built around -- watch it, react, change a number, watch it
again -- is only safe if you can get the last number back.

Two rules keep it out of your way:

  1. It commits exactly one path, the project's film.yaml. Whatever else
     you have staged or half-finished is never swept into the commit.
  2. It never fails loudly. No git, not a repository, git having a bad
     day -- every function here shrugs and returns None. A snapshot is
     not worth losing a render over.

To see the history of one film, and to get an old version back:

    git log --oneline -- projects/morning/film.yaml
    git show <sha>:projects/morning/film.yaml > projects/morning/film.yaml
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TIMEOUT = 10        # seconds. A hung git must not hang a render.


def _git(cwd: Path, *args: str):
    """Run git and read what it said, as UTF-8.

    Not text=True. That decodes with the machine's locale codepage, and
    git writes UTF-8 -- so on a Polish Windows a film called `Zima nad
    morzem` came back out of `git log` as `Zima nad morzem Ä…Ä™`.

    Cosmetic in the listing, and not cosmetic at all in `restore`, which
    returns a film.yaml: every accented letter in every caption would
    have been mangled on the way back in, by the one command whose whole
    job is undoing damage.
    """
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args],
                           capture_output=True, timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    r.stdout = (r.stdout or b"").decode("utf-8", errors="replace")
    r.stderr = (r.stderr or b"").decode("utf-8", errors="replace")
    return r


def repo_root(start: Path) -> Path | None:
    r = _git(start, "rev-parse", "--show-toplevel")
    if r is None or r.returncode != 0:
        return None
    top = r.stdout.strip()
    return Path(top) if top else None


def snapshot(project: Path, label: str) -> str | None:
    """Commit this project's film.yaml if it has changed.

    Returns the short sha if something was committed, None in every other
    case -- including "nothing changed", which is the common one.
    """
    yml = project / "film.yaml"
    if not yml.exists():
        return None

    root = repo_root(project)
    if root is None:
        return None
    try:
        rel = yml.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:                       # project lives outside the repo
        return None

    changed = _git(root, "status", "--porcelain", "--", rel)
    if changed is None or changed.returncode != 0 or not changed.stdout.strip():
        return None

    if _git(root, "add", "--", rel) is None:
        return None
    # `commit -- <path>` commits that path and nothing else, whatever else
    # happens to be staged.
    done = _git(root, "commit", "-m", f"{project.name}: {label}", "--", rel)
    if done is None or done.returncode != 0:
        return None

    sha = _git(root, "rev-parse", "--short", "HEAD")
    return sha.stdout.strip() if sha and sha.returncode == 0 else "committed"


def versions(project: Path, limit: int = 12) -> list[tuple[str, str]]:
    """Every saved version of this film.yaml, newest first, as
    (short sha, what was being rendered when it was saved).

    The snapshots have always been there; there was no way to see them
    that did not involve typing a git command with a path in it. The
    person this toolkit is for is not going to do that.
    """
    yml = project / "film.yaml"
    root = repo_root(project)
    if root is None or not yml.exists():
        return []
    try:
        rel = yml.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return []
    r = _git(root, "log", f"-{limit}", "--format=%h\t%s", "--", rel)
    if r is None or r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        sha, _, subject = line.partition("\t")
        if sha:
            out.append((sha.strip(), subject.strip()))
    return out


def restore(project: Path, sha: str) -> str | None:
    """Put a saved version of film.yaml back. Returns its text, or None.

    Writes nothing that will not load: the caller checks. Nothing else in
    the repository is touched -- this reads one file out of one commit.
    """
    yml = project / "film.yaml"
    root = repo_root(project)
    if root is None:
        return None
    try:
        rel = yml.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    r = _git(root, "show", f"{sha}:{rel}")
    if r is None or r.returncode != 0 or not r.stdout:
        return None
    return r.stdout
