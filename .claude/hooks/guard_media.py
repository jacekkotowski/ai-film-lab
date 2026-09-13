"""
guard_media.py  --  the originals are read-only, and this makes it true.

CLAUDE.md has always said "never touch media/". A sentence in a prompt
is a request: it works almost always, and "almost" is the wrong word for
someone's only copy of their photographs. So this runs BEFORE every
Edit / Write / NotebookEdit and refuses any path inside a project's
media/ folder. Claude sees the reason and carries on with something else.

Wired up in .claude/settings.json as a PreToolUse hook. Standard library
only -- a guard that needs `uv sync` to work is a guard that can fail.

Try it by hand (PowerShell):
    echo '{"tool_input":{"file_path":"projects/x/media/a.jpg"}}' | python .claude/hooks/guard_media.py
"""

import json
import sys
from pathlib import PurePath


def inside_media(path: str) -> bool:
    """True for projects/<film>/media/<anything>, however the path is spelled."""
    parts = [p.lower() for p in PurePath(path.replace("\\", "/")).parts]
    for i, part in enumerate(parts[:-2]):
        if part == "projects" and parts[i + 2] == "media":
            return True
    return False


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

    if not inside_media(path):
        return                                   # silence means "allowed"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{path} is an original in media/, and originals are read-only. "
                "Change film.yaml instead (in/out, crop, focus), or ask the "
                "user to replace the file themselves."
            ),
        }
    }))


if __name__ == "__main__":
    main()
