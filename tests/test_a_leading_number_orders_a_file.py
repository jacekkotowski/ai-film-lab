r"""
A leading number orders a file, with or without a separator.

Jacek's own test project, `projects/test_story`, held three pictures
named `1declaration_of_love.png`, `2declaration of love.png` and
`3_declaration_of_love.png`. They came out of `film init` in the order
3, 1, 2. Measured cause: `_NUM_PREFIX` required a separator after the
number (`^(\d{1,3})[_.\-\s]+`), so only the one with the underscore
was read as numbered -- it went first, and the other two followed
alphabetically behind it.

The header `film init` writes says `00_ 01_ ...  explicit order`. That
promise was kept only for the shape that happened to be written down.
So: a leading run of up to three digits is the order, and whatever
separates it from the name -- an underscore, a dot, a dash, a space or
nothing at all -- is not the point.

A longer run of digits is still not a number: `20260917.jpg` is a date
and `IMG_0042.jpg` is a camera's counter, and neither is somebody
asking for position 202 or 42.

Numbers and strings only. Nothing here touches ffmpeg or the disk.
"""

from ffilm import scaffold


def num(stem: str):
    return scaffold._hint(stem)[1]


def clean(stem: str):
    return scaffold._hint(stem)[2]


def test_a_number_with_no_separator_still_orders():
    assert num("1declaration_of_love") == 1
    assert num("2declaration of love") == 2
    assert num("3_declaration_of_love") == 3


def test_jaceks_three_pictures_come_out_one_two_three():
    stems = ["3_declaration_of_love", "1declaration_of_love",
             "2declaration of love"]
    assert sorted(stems, key=num) == ["1declaration_of_love",
                                      "2declaration of love",
                                      "3_declaration_of_love"]


def test_the_separator_is_not_part_of_the_name():
    """Whatever stands between the number and the name is dropped, so
    the role hints and the quote-card title read the same name either
    way."""
    assert clean("3_declaration_of_love") == "declaration_of_love"
    assert clean("1declaration_of_love") == "declaration_of_love"
    assert clean("03.beach") == "beach"
    assert clean("04 beach") == "beach"


def test_a_role_after_the_number_is_still_a_role():
    role, n, rest = scaffold._hint("03_open_close_logo")
    assert (role, n, rest) == ("open_close", 3, "logo")


def test_a_date_or_a_camera_counter_is_not_an_order():
    assert num("20260917") is None
    assert num("IMG_0042") is None
    assert num("PXL_20260827_113000") is None


def test_a_file_called_just_a_number_is_that_number():
    assert num("5") == 5
    assert num("12") == 12
