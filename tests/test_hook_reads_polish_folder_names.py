"""The check_film hook must find a film whose folder name is Polish.

Claude Code hands the hook its event as UTF-8 bytes. Read with Windows'
own code page, "ł" (two bytes in UTF-8) came out as "Å‚", no folder has
that name, and every edit to the Frankfurt vs Kołakowski film.yaml was
reported as a failed `film check` although the film was fine.
"""

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "check_film.py"


def load_hook():
    spec = importlib.util.spec_from_file_location("check_film", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_polish_folder_name_survives_the_trip_into_the_hook():
    hook = load_hook()
    path = "C:/x/projects/Frankfurt School vs Kołakowski/film.yaml"
    raw = json.dumps({"tool_input": {"file_path": path}},
                     ensure_ascii=False).encode("utf-8")
    project = hook.edited_film(hook.read_event(raw))
    assert project.name == "Frankfurt School vs Kołakowski"
