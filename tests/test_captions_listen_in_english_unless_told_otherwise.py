"""
2026-09-29, "It Reads Us - We Can't Read It": the English intro opens on
two Polish names, and the speech model, left to guess, said Polish
(probability 0.49) and captioned the whole intro in made-up Polish. Told
"en", the same take came out right. So a caption listens in English
unless `--lang` says otherwise.

No model here: a stand-in records the language it was asked for.
"""

import sys
import types
from pathlib import Path

from ffilm import voice


def _asked_language(monkeypatch, **kw) -> str | None:
    asked = {}

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **k):
            asked["language"] = k.get("language")
            return iter([]), types.SimpleNamespace(language=k.get("language"))

    monkeypatch.setitem(sys.modules, "faster_whisper",
                        types.SimpleNamespace(WhisperModel=FakeModel))
    voice.transcribe(Path("take.wav"), **kw)
    return asked["language"]


def test_no_language_given_means_english(monkeypatch):
    assert _asked_language(monkeypatch) == "en"


def test_no_language_given_with_a_script_means_english(monkeypatch):
    assert _asked_language(monkeypatch, script="Michal Kosinski measures.") == "en"


def test_a_language_given_is_used(monkeypatch):
    assert _asked_language(monkeypatch, language="pl") == "pl"
