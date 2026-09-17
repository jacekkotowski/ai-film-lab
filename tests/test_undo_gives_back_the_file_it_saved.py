"""
`film undo` was doubling every line ending.

Found by the acceptance run of the 2026-09-17 Plan B, on test_story: the
file came back with exactly the right content and 145 blank lines that
were not there before. Measured on the bytes: 145 line endings, every
one of them `\\r\\r\\n`.

The mechanism, all on Windows:

  `git show sha:film.yaml` hands back the blob, and the blob has CRLF
  in it because that is how it was committed;
  `_git` decodes those bytes to text without touching them, which is
  right -- it is fixing a different bug, see its own docstring;
  `Path.write_text` opens in text mode, where Python translates every
  `\\n` it is given into `os.linesep`. The `\\r` already in front of it
  stays. `\\r\\n` goes in, `\\r\\r\\n` comes out.

It doubles again on every undo of an undo. YAML tolerates it, so the
film still loaded and nothing said a word.

The same cause broke the "nothing to undo" check just above the write:
that compares the restored text against `read_text`, which translates
line endings on the way IN, so a CRLF blob never equalled the identical
file on disk and `undo` always claimed to have changed something.

So: git's bytes are data, and the one place they become a file decides
the line endings, once.

Strings only. Nothing runs git.
"""

from ffilm.history import one_newline


def test_windows_line_endings_come_back_as_one_newline():
    assert one_newline("a\r\nb\r\n") == "a\nb\n"


def test_a_file_that_was_already_plain_is_untouched():
    assert one_newline("a\nb\n") == "a\nb\n"


def test_an_old_mac_ending_counts_as_one_too():
    assert one_newline("a\rb\r") == "a\nb\n"


def test_the_doubled_ending_this_was_written_for_is_undone():
    """A film.yaml that a previous undo already mangled is repaired by
    the next one rather than mangled further."""
    assert one_newline("a\r\r\nb\r\r\n") == "a\n\nb\n\n"


def test_nothing_but_the_endings_changes():
    yaml = ('# Zima nad morzem\r\nshots:\r\n  - id: s01\r\n'
            '    src: media/a.png\r\n')
    out = one_newline(yaml)
    assert out.splitlines() == yaml.splitlines()
    assert "\r" not in out
