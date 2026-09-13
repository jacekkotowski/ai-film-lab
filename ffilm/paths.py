"""
paths.py  --  where the toolkit is on this disk.

One function, so that the answer is worked out in one place. Three
modules used to compute it from their own __file__, each assuming it
sat exactly one folder below the toolkit.
"""

from pathlib import Path


def toolkit_root() -> Path:
    """Where ffilm itself lives, no matter which folder the terminal is in."""
    return Path(__file__).resolve().parent.parent
