"""
Recording from a camera and a microphone.

The samples below are real output from a real machine -- a Polish
Windows laptop with an EasyCamera, a Realtek microphone whose name
contains a letter that is not in ASCII, and OBS installed but shut.
Every one of those is a thing that has broken this kind of code before,
which is why they are here rather than a tidy invented example.

None of this opens a device. It is parsing and flag-building only.
"""

import pytest

from ffilm import record
from ffilm.record import (Device, best_mode, choose_devices, escape_device,
                          input_spec, is_recording, parse_devices,
                          parse_modes, record_command, take_name)
from ffilm.scaffold import _speed_for


# Newer ffmpeg: every device tagged inline with its kind.
NEW_FORMAT = '''\
[in#0 @ 00000234cfcbe2c0] "EasyCamera" (video)
[in#0 @ 00000234cfcbe2c0]   Alternative name "@device_pnp_\\\\?\\usb#vid_04f2"
[in#0 @ 00000234cfcbe2c0] "OBS Virtual Camera" (none)
[in#0 @ 00000234cfcbe2c0]   Alternative name "@device_sw_{860BB310}"
[in#0 @ 00000234cfcbe2c0] "Zestaw mikrofonów (Realtek High Definition Audio)" (audio)
[in#0 @ 00000234cfcbe2c0]   Alternative name "@device_cm_{33D9A762}"
[in#0 @ 00000234cfcbe2c0] "Mikrofon (Steam Streaming Microphone)" (audio)
Error opening input file dummy.
'''

# Older ffmpeg: section headings, and the kind has to be carried down.
OLD_FORMAT = '''\
[dshow @ 000001] DirectShow video devices (some may be both video and audio)
[dshow @ 000001]  "Integrated Camera"
[dshow @ 000001]     Alternative name "@device_pnp_\\\\?\\usb#vid_0000"
[dshow @ 000001] DirectShow audio devices
[dshow @ 000001]  "Microphone (Realtek High Definition Audio)"
[dshow @ 000001]     Alternative name "@device_cm_{33D9A762}"
'''

MODES = '''\
[dshow @ 01] vcodec=mjpeg min s=1280x720 fps=10 max s=1280x720 fps=30
[dshow @ 01] pixel_format=yuyv422 min s=640x480 fps=30 max s=640x480 fps=30
[dshow @ 01] pixel_format=yuyv422 min s=800x600 fps=15 max s=800x600 fps=30
'''


# --------------------------------------------------------------------------
# Reading the device list
# --------------------------------------------------------------------------

def test_the_current_ffmpeg_format_is_understood():
    devices = parse_devices(NEW_FORMAT)
    assert [d.name for d in devices if d.kind == "video"] == ["EasyCamera"]
    assert len([d for d in devices if d.kind == "audio"]) == 2


def test_a_non_ascii_device_name_survives_intact():
    """The name is not just printed -- it is handed straight back to
    ffmpeg to open the device. A mangled one opens nothing, and the
    failure never happens on an English machine."""
    devices = parse_devices(NEW_FORMAT)
    mics = [d.name for d in devices if d.kind == "audio"]
    assert "Zestaw mikrofonów (Realtek High Definition Audio)" in mics


def test_the_older_ffmpeg_format_still_works():
    """A machine you sit down at may have any build on it."""
    devices = parse_devices(OLD_FORMAT)
    assert [d.name for d in devices if d.kind == "video"] == \
        ["Integrated Camera"]
    assert [d.name for d in devices if d.kind == "audio"] == \
        ["Microphone (Realtek High Definition Audio)"]


def test_alternative_names_are_never_mistaken_for_devices():
    for text in (NEW_FORMAT, OLD_FORMAT):
        assert not any("device_pnp" in d.name or "device_cm" in d.name
                       for d in parse_devices(text))


def test_a_dormant_virtual_camera_is_listed_but_not_usable():
    """OBS registers its virtual camera whether OBS is running or not.
    Defaulting to it records a grey rectangle."""
    obs = next(d for d in parse_devices(NEW_FORMAT)
               if d.name == "OBS Virtual Camera")
    assert obs.kind == "none"
    assert not obs.usable


def test_nothing_plugged_in_is_an_empty_list_not_a_crash():
    assert parse_devices("") == []


# --------------------------------------------------------------------------
# Negotiating a capture mode
# --------------------------------------------------------------------------

def test_the_modes_a_camera_offers_are_read_without_duplicates():
    modes = parse_modes(MODES)
    assert (1280, 720, 30.0) in modes
    assert len(modes) == len(set(modes))


def test_the_biggest_mode_that_still_moves_properly_wins():
    """1280x720 is offered at both 10fps and 30fps. Picking the entry
    with the most pixels without looking at fps gives a slideshow."""
    assert best_mode(parse_modes(MODES)) == (1280, 720, 30.0)


def test_a_camera_offering_nothing_sensible_gets_no_flags_at_all():
    """Better the camera's own default than a guess that fails to open."""
    assert best_mode([(1280, 720, 10.0), (640, 480, 15.0)]) is None
    assert best_mode([]) is None


def test_an_enormous_camera_is_capped():
    modes = [(3840, 2160, 30.0), (1920, 1080, 30.0)]
    assert best_mode(modes) == (1920, 1080, 30.0)


# --------------------------------------------------------------------------
# Naming devices to ffmpeg
# --------------------------------------------------------------------------

def test_a_colon_in_a_device_name_is_escaped():
    """dshow splits video=X:audio=Y on the colon, so an unescaped one
    silently truncates the device name."""
    assert escape_device("Cam: the good one") == "Cam\\: the good one"


def test_backslashes_are_doubled():
    assert escape_device("a\\b") == "a\\\\b"


def test_an_ordinary_name_is_left_exactly_alone():
    name = "Zestaw mikrofonów (Realtek High Definition Audio)"
    assert escape_device(name) == name


def test_the_input_names_both_devices():
    assert input_spec("Cam", "Mic") == "video=Cam:audio=Mic"


# --------------------------------------------------------------------------
# The capture command
# --------------------------------------------------------------------------

def cmd(**kw):
    kw.setdefault("out", record.Path("take.mp4"))
    kw.setdefault("video", "Cam")
    kw.setdefault("audio", "Mic")
    return record_command(**kw)


def test_the_negotiated_mode_is_passed_to_the_camera():
    c = cmd(mode=(1280, 720, 30.0))
    assert "-video_size" in c and "1280x720" in c
    assert "30" in c[c.index("-framerate") + 1]


def test_no_mode_means_no_size_flags():
    c = cmd(mode=None)
    assert "-video_size" not in c and "-framerate" not in c


def test_the_buffer_is_generous_because_dropped_frames_are_gone_for_good():
    assert "-rtbufsize" in cmd()


def test_a_microphone_only_take_asks_for_no_video():
    c = record_command(record.Path("v.m4a"), None, "Mic")
    assert "-vn" in c and "video=" not in " ".join(c)


def test_a_silent_camera_take_asks_for_no_audio():
    c = record_command(record.Path("v.mp4"), "Cam", None)
    assert "-an" in c and "audio=" not in " ".join(c)


def test_recording_nothing_at_all_is_refused_rather_than_attempted():
    with pytest.raises(ValueError):
        record_command(record.Path("v.mp4"), None, None)


def test_a_fixed_length_take_stops_itself():
    assert "-t" in cmd(seconds=4)


def test_the_console_is_kept_quiet():
    """You are talking to a lens. A wall of scrolling ffmpeg statistics
    is not feedback, it is a distraction."""
    assert "-nostats" in cmd()


def test_the_pixel_format_is_one_that_actually_plays():
    """Webcams hand over yuvj420p, which plenty of players refuse."""
    c = cmd()
    assert c[c.index("-pix_fmt") + 1] == "yuv420p"


# --------------------------------------------------------------------------
# Which devices, on a machine that is not the one you set this up on
# --------------------------------------------------------------------------

HERE = [Device("EasyCamera", "video"), Device("OBS Virtual Camera", "none"),
        Device("Realtek Mic", "audio"), Device("Steam Mic", "audio")]


def test_with_no_history_it_just_picks_something_that_works():
    video, audio, _ = choose_devices(HERE, saved={})
    assert video == "EasyCamera"
    assert audio == "Realtek Mic"


def test_a_dormant_device_is_never_chosen_by_default():
    video, _, _ = choose_devices(HERE, saved={})
    assert video != "OBS Virtual Camera"


def test_what_you_chose_last_time_is_used_again():
    _, audio, _ = choose_devices(HERE, saved={"audio": "Steam Mic"})
    assert audio == "Steam Mic"


def test_a_remembered_device_from_another_machine_is_not_an_error():
    """The whole point of taking this to a second computer. The old
    choice is simply not here, and that is a different desk, not a
    fault -- it says so once and carries on."""
    video, audio, notes = choose_devices(
        HERE, saved={"video": "Logitech C920", "audio": "Blue Yeti"})
    assert video == "EasyCamera"
    assert audio == "Realtek Mic"
    assert any("not on this computer" in n for n in notes)


def test_asking_for_a_device_that_is_not_here_says_so_plainly():
    with pytest.raises(SystemExit) as e:
        choose_devices(HERE, saved={}, want_video="Logitech C920")
    assert "Logitech C920" in str(e.value)
    assert "EasyCamera" in str(e.value)


def test_a_machine_with_no_camera_can_still_record_sound():
    mics = [d for d in HERE if d.kind == "audio"]
    video, audio, _ = choose_devices(mics, saved={})
    assert video is None
    assert audio == "Realtek Mic"


# --------------------------------------------------------------------------
# A recorded take arrives in the edit already sped up
# --------------------------------------------------------------------------

def test_a_take_names_itself_so_the_edit_can_recognise_it():
    assert is_recording(take_name().replace(".mp4", ""))


def test_takes_sort_chronologically_as_plain_text():
    from datetime import datetime
    a = take_name(datetime(2026, 8, 28, 9, 5, 0))
    b = take_name(datetime(2026, 8, 28, 10, 5, 0))
    assert a < b


def test_a_recorded_take_comes_into_the_edit_at_the_faster_speed():
    assert _speed_for("media/rec_20260828-101840.mp4") == record.REC_SPEED


def test_footage_from_a_phone_or_a_camera_is_left_completely_alone():
    """This is a correction for talking to a lens, not a house style."""
    assert _speed_for("media/holiday.mp4") == 1.0
    assert _speed_for("media/02_2026-08-27 21-31-48.mkv") == 1.0


# --------------------------------------------------------------------------
# The recording window: preview, level, and the scrolling script
# --------------------------------------------------------------------------

from ffilm import booth


def test_the_window_reports_honestly_whether_it_can_open():
    assert isinstance(booth.available(), bool)


def wrapped(*lines):
    """Lines as a window would leave them: every one but the last full."""
    return "\n".join(lines)


def test_a_script_hard_wrapped_in_notepad_is_joined_back_up():
    """Wrap breaks land mid-sentence and the eye trips on each."""
    out = booth.reflow(wrapped(
        "There are mornings when getting out of bed is the whole of it,",
        "and nobody is going to hand you a medal for having managed it,",
        "so you will have to be the one."))
    assert "\n" not in out
    assert out.startswith("There are mornings when getting out of bed")


def test_the_line_breaks_you_typed_yourself_are_kept():
    """Short lines are breaths. Flattening them makes a prompter read a
    list of separate thoughts out as one long sentence."""
    script = "You are enough.\nYou always were.\nEven this morning."
    assert booth.reflow(script) == script


def test_one_short_line_in_a_block_keeps_the_whole_block():
    """It can only have been put there on purpose, so nothing in that
    block was a window's doing."""
    script = wrapped(
        "There are mornings when getting out of bed is the whole of it,",
        "and that is fine.",
        "So you will have to be the one.")
    assert booth.reflow(script) == script


def test_the_gaps_between_paragraphs_are_kept():
    out = booth.reflow("First thing.\n\nSecond thing.")
    assert out == "First thing.\n\nSecond thing."


def test_a_single_line_is_never_treated_as_a_wrap():
    assert booth.reflow("Just the one thing.") == "Just the one thing."


def test_trailing_spaces_do_not_survive_into_the_prompter(tmp_path):
    """Centred text with invisible trailing spaces sits off-centre."""
    assert booth.reflow("  You are enough.  \n   You always were. ") == \
        "You are enough.\nYou always were."


def test_an_empty_script_stays_empty():
    assert booth.reflow("") == ""
    assert booth.reflow("\n\n   \n") == ""


def test_no_script_file_is_not_an_error(tmp_path):
    """Recording without a script is the ordinary case."""
    assert booth.read_script(tmp_path, None) == ""


def test_a_script_in_the_project_is_found_without_being_asked_for(tmp_path):
    (tmp_path / "script.txt").write_text("Say\nthis.", encoding="utf-8")
    assert booth.read_script(tmp_path, None) == "Say\nthis."


def test_an_explicit_script_beats_the_one_in_the_project(tmp_path):
    (tmp_path / "script.txt").write_text("wrong", encoding="utf-8")
    (tmp_path / "other.txt").write_text("right", encoding="utf-8")
    assert booth.read_script(tmp_path, "other.txt") == "right"


def test_a_missing_script_says_so_rather_than_recording_in_silence(tmp_path):
    with pytest.raises(SystemExit):
        booth.read_script(tmp_path, "nope.txt")


def test_reading_faster_scrolls_faster():
    slow = booth.scroll_speed("one two three four", 60, 1000)
    fast = booth.scroll_speed("one two three four", 120, 1000)
    assert fast > slow


def test_the_same_reading_speed_means_the_same_thing_for_any_length():
    """Set as words per minute, not pixels per second, so a forty-word
    script and a four-hundred-word one both go by at reading pace."""
    short = booth.scroll_speed("word " * 40, 100, 1000)
    long = booth.scroll_speed("word " * 400, 100, 10000)
    assert abs(short - long) < 1e-6


def test_the_words_take_exactly_as_long_as_they_say_they_will():
    """100 words at 100 wpm is one minute of scrolling, and the arithmetic
    has to come out at 60 seconds -- not 60 minus however much screen the
    words have to cross afterwards. That padding used to be folded into
    the distance here, which turned "105 words a minute" into about 170."""
    text_px = 4000.0
    px_per_sec = booth.scroll_speed("word " * 100, 100, text_px)
    assert abs(text_px / px_per_sec - 60.0) < 1e-6


def test_the_lead_out_does_not_speed_up_the_reading():
    """Whatever empty screen the last line crosses on its way off the top,
    it crosses at the same pace the words were read at."""
    words = "word " * 100
    assert booth.scroll_speed(words, 100, 4000.0) == \
        booth.scroll_speed(words, 100, 4000.0)
    # A taller block of the same words would mean bigger type, and bigger
    # type does have further to travel -- that part is real.
    assert booth.scroll_speed(words, 100, 8000.0) > \
        booth.scroll_speed(words, 100, 4000.0)


# --------------------------------------------------------------------------
# The capture that also feeds the window
# --------------------------------------------------------------------------

def test_the_window_gets_its_own_copy_of_the_picture():
    c = cmd(window=True)
    assert "rawvideo" in c and "pipe:1" in c


def test_the_window_gets_a_loudness_reading():
    c = cmd(window=True)
    assert any("ebur128" in x for x in c)


def test_the_log_is_turned_up_far_enough_for_the_meter_to_read_it():
    """At the ordinary quiet level there is no log, and the level bar
    would sit at silence however loudly you spoke."""
    assert cmd(window=True)[cmd(window=True).index("-loglevel") + 1] == "info"


def test_without_the_window_nothing_extra_is_computed():
    c = cmd(window=False)
    assert "pipe:1" not in c
    assert not any("ebur128" in x for x in c)
    assert c[c.index("-loglevel") + 1] == "error"


def test_the_streams_are_mapped_explicitly_once_there_is_a_preview():
    """Left automatic, ffmpeg puts the video into the metering output
    too -- work done only to be thrown away."""
    assert "-map" in cmd(window=True)


def test_the_picture_is_decoded_once_and_split_not_mapped_twice():
    """The bug this exists to prevent, and it was silent: naming
    `-map 0:v` in both the file output and the preview output starves
    the recording. Measured -- 7.5 seconds in front of the camera came
    out as a 1.8 second file, against 7.2 with `split`. A preview is a
    convenience; paying three quarters of what somebody said for it is
    not a trade anybody would agree to."""
    c = cmd(window=True)
    assert any("split=2" in x for x in c)
    assert c.count("0:v") == 0          # nothing maps the raw stream twice
    assert "[main]" in c and "[pw]" in c


def test_a_timed_take_is_left_to_the_window_when_there_is_one():
    """Measured: -t before -i ends the capture cleanly with one output,
    and does NOT end it once the preview is attached -- ffmpeg sits
    there. So the window sends the same `q` that SPACE sends, and only
    one shutdown path has to be right."""
    assert "-t" not in cmd(window=True, seconds=5)


def test_without_a_window_ffmpeg_times_itself():
    c = cmd(window=False, seconds=5)
    assert c.index("-t") < c.index("-i")


def test_two_takes_in_the_same_second_do_not_overwrite_each_other(tmp_path):
    """The cost of being wrong here is somebody's first take."""
    first = record.next_take_path(tmp_path)
    first.write_bytes(b"x")
    second = record.next_take_path(tmp_path)
    assert second != first
    assert record.is_recording(second.stem)


# --------------------------------------------------------------------------
# Why a take came out slow
# --------------------------------------------------------------------------

def test_a_take_at_the_full_rate_says_nothing():
    assert record.rate_note(29.9, 30) == []
    assert record.rate_note(27.0, 30) == []


def test_half_the_rate_is_blamed_on_the_light_not_the_computer():
    """Measured on this machine: 2299 frames over 76.9s at brightness 108,
    then 92 frames over 6.3s at brightness 52. Both halved together. The
    camera holds the shutter open longer and hands back half the frames."""
    note = record.rate_note(15.1, 30)[0]
    assert "light" in note
    assert "Nothing is wrong with the computer" in note


def test_a_third_of_the_rate_is_the_same_story():
    assert "light" in record.rate_note(10.0, 30)[0]


def test_an_odd_rate_really_is_the_machine():
    """22 of 30 is not a step on any exposure ladder."""
    note = record.rate_note(19.0, 30)[0]
    assert "could not keep up" in note


def test_the_old_message_never_fires_on_a_clean_halving():
    """The bug this replaces: being told to close programs and buy a
    faster computer when the answer was a lamp."""
    for got, asked in ((15.0, 30), (12.0, 24), (7.5, 30)):
        assert "could not keep up" not in " ".join(
            record.rate_note(got, asked))
