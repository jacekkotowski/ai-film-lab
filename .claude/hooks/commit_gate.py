"""
commit_gate.py  --  no turn ends with the machine changed and not committed.

2026-09-23: fixes sat uncommitted for hours, and "is it done?" had no
answer on disk. Stop hook: if ffilm/ or tests/ has uncommitted changes,
Claude is sent back once to (a) run the proof on Jacek's real file,
(b) commit with the proof in the message, or (c) say in the FIRST line
of the answer that it is NOT committed and why. `stop_hook_active`
lets the second stop through, so it can never loop.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    event = json.load(sys.stdin)
    if event.get("stop_hook_active"):
        return
    run = subprocess.run(["git", "status", "--porcelain", "--", "ffilm",
                          "tests"], cwd=ROOT, capture_output=True, text=True)
    changed = [l for l in run.stdout.splitlines() if l.strip()]
    if not changed:
        return
    print("ffilm/ or tests/ has UNCOMMITTED changes:\n  "
          + "\n  ".join(changed[:10])
          + "\n\nBefore ending: show the proof on Jacek's real file, then "
            "commit with that proof in the message. If you cannot, the "
            "FIRST line of your answer says: NOT COMMITTED, and why.",
          file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
