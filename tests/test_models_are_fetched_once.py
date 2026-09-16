"""
Model files: fetched once into models/, checked, never committed.

A new computer must not need anybody to download anything by hand, and
a download that came down wrong must never be used. No network here: the
download is a fake that hands back whatever bytes the test chooses.
"""

import hashlib
import io
import re
from dataclasses import replace

import pytest

from ffilm import models
from ffilm.paths import toolkit_root

PAYLOAD = b"rnnoise-nu model file version 1\n" + bytes(range(256)) * 4
FAKE = replace(models.SPEECH_DENOISE, size=len(PAYLOAD),
               sha256=hashlib.sha256(PAYLOAD).hexdigest())


@pytest.fixture(autouse=True)
def fresh_run():
    """A failed download is remembered for the rest of a run, so that a
    film of forty shots does not wait out forty network timeouts. Each
    test is its own run."""
    models._given_up.clear()
    yield
    models._given_up.clear()


def test_a_failed_download_is_not_retried_by_every_shot(tmp_path):
    opener = Opener(fail=True)
    for _ in range(5):
        models.ensure(FAKE, tmp_path, say=lambda s: None, opener=opener)
    assert opener.calls == 1


class Opener:
    def __init__(self, data=PAYLOAD, fail=False):
        self.data, self.fail, self.calls = data, fail, 0

    def __call__(self, url, timeout=None):
        self.calls += 1
        if self.fail:
            raise OSError("no network")
        return io.BytesIO(self.data)


def test_a_missing_model_is_downloaded_into_the_models_folder(tmp_path):
    opener = Opener()
    path = models.ensure(FAKE, tmp_path, say=lambda s: None, opener=opener)
    assert path == tmp_path / FAKE.file
    assert path.read_bytes() == PAYLOAD
    assert opener.calls == 1


def test_a_model_already_there_is_not_downloaded_again(tmp_path):
    (tmp_path / FAKE.file).write_bytes(PAYLOAD)
    opener = Opener()
    assert models.ensure(FAKE, tmp_path, say=lambda s: None, opener=opener)
    assert opener.calls == 0


def test_a_wrong_download_is_refused_and_leaves_nothing_behind(tmp_path):
    opener = Opener(data=PAYLOAD[:-1] + b"!")
    assert models.ensure(FAKE, tmp_path, say=lambda s: None, opener=opener) is None
    assert list(tmp_path.iterdir()) == []


def test_a_half_downloaded_file_counts_as_missing(tmp_path):
    (tmp_path / FAKE.file).write_bytes(PAYLOAD[:10])
    assert not models.is_present(FAKE, tmp_path)
    assert models.ensure(FAKE, tmp_path, say=lambda s: None, opener=Opener())
    assert models.is_present(FAKE, tmp_path)


def test_without_a_network_it_says_so_and_carries_on(tmp_path):
    said = []
    assert models.ensure(FAKE, tmp_path, say=said.append,
                         opener=Opener(fail=True)) is None
    assert any("film models" in s for s in said)


def test_the_folder_can_be_moved(tmp_path, monkeypatch):
    monkeypatch.setenv("FFILM_MODELS", str(tmp_path))
    assert models.models_dir() == tmp_path


def test_every_model_in_the_code_is_listed_in_the_readme_with_its_checksum():
    """The README is what a person reads; the catalogue is what runs.
    They must say the same thing."""
    readme = (toolkit_root() / "models" / "README.md").read_text(encoding="utf-8")
    for m in models.CATALOGUE:
        assert m.file in readme and m.sha256 in readme
        assert m.url in re.findall(r"https://\S+", readme)


def test_model_files_are_never_committed():
    ignore = (toolkit_root() / ".gitignore").read_text(encoding="utf-8")
    assert "models/*" in ignore and "!models/README.md" in ignore
