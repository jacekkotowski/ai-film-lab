"""
Shared setup for the tests.

The one thing that matters here: the shared library -- the folder whose
music backs every film -- must not be the real one while the tests run.
Without this, a suite that builds a film in a temporary folder would pass
or fail depending on whether there happens to be an mp3 on this machine,
and the failure would arrive weeks later on somebody else's computer.
"""

import pytest


@pytest.fixture(autouse=True)
def empty_shelf(tmp_path_factory, monkeypatch):
    """Every test starts with a library that exists and is empty."""
    shelf = tmp_path_factory.mktemp("library")
    (shelf / "music").mkdir()
    (shelf / "cover").mkdir()
    monkeypatch.setenv("FFILM_LIBRARY", str(shelf))
    return shelf


@pytest.fixture
def shelf(empty_shelf):
    """The same folder, for tests that want to put something on it."""
    return empty_shelf
