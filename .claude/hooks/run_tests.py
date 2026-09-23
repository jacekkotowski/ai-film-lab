"""
run_tests.py  --  every edit to the machine runs the tests, the moment it lands.

2026-09-23: "run the tests after a change" was a sentence in ffilm/CLAUDE.md,
and a sentence is what gets skipped in a long session. PostToolUse on
Edit|Write: if the file is ffilm/*.py or tests/*.py, the whole suite runs
(under a few seconds). A failure -> exit 2, and Claude must fix it before
anything else. Standard library only.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    if not path:
        return
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    try:
        rel = p.resolve().relative_to(ROOT)
    except ValueError:
        return
    if p.suffix != ".py" or rel.parts[0] not in ("ffilm", "tests"):
        return
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = subprocess.run(
        ["uv", "run", "--quiet", "--extra", "dev", "pytest", "-q", "-x",
         "-p", "no:warnings"],
        cwd=ROOT, env=env, capture_output=True, timeout=110)
    out = (run.stdout + run.stderr).decode("utf-8", errors="replace")
    if run.returncode != 0:
        tail = "\n".join(out.strip().splitlines()[-40:])
        print(f"TESTS FAIL after editing {rel}. Fix before anything else:"
              f"\n\n{tail}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
