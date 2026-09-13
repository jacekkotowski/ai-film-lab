"""
check_film.py  --  every edit to a film.yaml is checked the moment it lands.

CLAUDE.md used to say "run `uv run film check` afterwards, always". An
instruction that must happen *every* time is exactly the kind a model
eventually skips, so this runs it instead: AFTER each Edit / Write, if
the file was projects/<film>/film.yaml, it runs `film check` on that film
and hands the output back to Claude.

  - check fails (bad YAML, a missing file)  -> exit 2: Claude is told to
                                               fix it before doing anything else
  - check passes                            -> its report (unused media,
                                               framing warnings) is added to
                                               Claude's context

Wired up in .claude/settings.json as a PostToolUse hook. Standard library
only.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]       # the toolkit folder
REPORT_LINES = 60                                # enough for any real film


def edited_film(event: dict) -> Path | None:
    path = event.get("tool_input", {}).get("file_path", "")
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if p.name != "film.yaml" or p.parent.parent.name != "projects":
        return None
    return p.parent


def main() -> None:
    project = edited_film(json.load(sys.stdin))
    if project is None:
        return

    env = dict(os.environ, PYTHONIOENCODING="utf-8")   # film names can be Polish
    run = subprocess.run(
        ["uv", "run", "--quiet", "film", "check", "-p", str(project)],
        cwd=ROOT, env=env, capture_output=True, timeout=110,
    )
    out = (run.stdout + run.stderr).decode("utf-8", errors="replace")
    report = "\n".join(out.strip().splitlines()[:REPORT_LINES])

    if run.returncode != 0:
        print(f"`film check` FAILED for {project.name} after this edit. "
              f"Fix film.yaml before anything else:\n\n{report}",
              file=sys.stderr)
        sys.exit(2)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"`film check` on {project.name}:\n{report}",
        }
    }))


if __name__ == "__main__":
    main()
