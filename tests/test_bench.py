"""
The editing bench, and the two ways it used to trap you.

A render takes ten or twenty seconds, and a browser tab can be closed
inside that window. That is ordinary. It used to print forty lines of
traceback -- and worse, the handler reporting the first failure wrote to
the same dead socket and failed again, so the second exception escaped.

The other trap was the way out. Ctrl+C is fine in a bare terminal, but
inside FILM.bat it asks Windows to terminate the batch job, which closes
the whole window and takes the guide with it.
"""

from ffilm.editor import PAGE, Bench


class Quiet(Bench):
    def __init__(self):
        pass                       # no socket; we only want handle_error



class Quiet(Bench):
    def __init__(self):
        pass                       # no socket; we only want handle_error


def test_a_browser_hanging_up_prints_nothing(capsys):
    """A render takes ten or twenty seconds and a tab can be closed
    inside that window. The default handler prints a traceback for every
    dropped connection, which is how a working bench came to look like a
    crashing one."""
    for boom in (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
        try:
            raise boom()
        except boom:
            Quiet().handle_error(None, ("127.0.0.1", 1))
    out = capsys.readouterr()
    assert out.err == "" and out.out == ""


def test_a_real_fault_is_still_reported(capsys):
    """Silencing dropped connections must not silence bugs."""
    try:
        raise ValueError("something actually wrong")
    except ValueError:
        Quiet().handle_error(None, ("127.0.0.1", 1))
    assert "ValueError" in capsys.readouterr().err


def test_the_bench_offers_a_way_out_that_is_not_ctrl_c():
    """Ctrl+C inside FILM.bat asks Windows to terminate the batch job,
    which closes the whole window and takes the guide with it."""
    assert 'id="done"' in PAGE
    assert "api/quit" in PAGE
