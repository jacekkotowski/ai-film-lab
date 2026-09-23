"""
long_session.py  --  a long session says so, before details get lost.

2026-09-23: one session ran a whole day; every message re-sent all of it,
the context was compressed, and details got lost -- which looks exactly
like forgetting. UserPromptSubmit: when the transcript passes LIMIT_MB,
Claude is told to finish the current task, commit, update docs/OPEN.md,
and tell Jacek in one line to start a new session.
"""

import json
import os
import sys

LIMIT_MB = 1.5


def main() -> None:
    event = json.load(sys.stdin)
    path = event.get("transcript_path") or ""
    try:
        mb = os.path.getsize(path) / 1e6
    except OSError:
        return
    if mb < LIMIT_MB:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            f"This session is long ({mb:.1f} MB). Finish only the current "
            "task, commit it, update docs/OPEN.md, then end your answer "
            "with ONE line telling Jacek to start a new session (it is "
            "cheaper, and nothing is lost: OPEN.md, docs/tech and git "
            "carry it).")}}))


if __name__ == "__main__":
    main()
