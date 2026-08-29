"""
The last few frames, which are usually not there.

A container is stamped with the length of its LONGEST stream. A webcam
recording stops when it stops, so a file whose picture ends at 49.83s
routinely reports 50.10 -- the audio ran on a little, or the muxer
rounded up. Both halves of this file are about the eight frames in that
gap: not writing an edit that asks for them, and not making a noise when
something else does.

No video files are opened here. The reader is driven with a stand-in
capture, so this stays as fast as the rest of the suite.
"""

import numpy as np

from ffilm.ingest import picture_duration
from ffilm.render import VideoSource
from ffilm.spec import Shot


# --------------------------------------------------------------------------
# How long there are pictures for
# --------------------------------------------------------------------------

def probed(container=None, stream=None, frames=None):
    v = {}
    if stream is not None:
        v["duration"] = stream
    if frames is not None:
        v["nb_frames"] = frames
    return ({"format": {"duration": container}} if container else {}), v


def test_the_pictures_end_before_the_file_does():
    """The actual numbers off a recording made by `film record`."""
    d, v = probed(container="50.099950", stream="49.866617", frames="1496")
    assert picture_duration(d, v, 30.0) == 49.87


def test_the_frame_count_is_used_when_the_stream_will_not_say():
    d, v = probed(container="50.10", frames="1496")
    assert picture_duration(d, v, 30.0) == 49.87


def test_the_container_is_the_last_resort_not_the_first():
    """It is the answer that is always there and sometimes wrong."""
    d, v = probed(container="50.10")
    assert picture_duration(d, v, 30.0) == 50.1


def test_a_zero_duration_is_not_an_answer():
    """ffprobe writes 0 and "N/A" for a stream it could not measure.
    Taking either literally makes every shot from that clip vanish."""
    d, v = probed(container="50.10", stream="0", frames="N/A")
    assert picture_duration(d, v, 30.0) == 50.1


def test_a_file_nothing_could_be_read_from_is_zero_not_a_crash():
    assert picture_duration({}, {}, 30.0) == 0.0


# --------------------------------------------------------------------------
# Asking for a frame that is not there
# --------------------------------------------------------------------------

class Tape:
    """A capture with a fixed number of frames and a loud complaint if
    anybody retrieves past the end -- which is what OpenCV does, in five
    lines of C++ straight over the top of the progress bar."""

    def __init__(self, frames: int):
        self.frames, self.at = frames, 0
        self.grabbed = True              # nothing has failed yet
        self.retrieved_past_end = False

    def get(self, _prop):
        return 30.0

    def set(self, _prop, value):
        self.at = int(value)

    def grab(self):
        # Exactly OpenCV's contract: grab moves to the next picture and
        # buffers it. Past the end there is no picture to buffer.
        self.grabbed = self.at < self.frames
        if self.grabbed:
            self.at += 1
        return self.grabbed

    def retrieve(self):
        # And retrieve decodes whatever grab last buffered. After a grab
        # that failed there is nothing there, which is the moment OpenCV
        # writes "Picture does not contain data" to stderr.
        if not self.grabbed:
            self.retrieved_past_end = True
            return False, None
        return True, np.zeros((16, 16, 3), dtype=np.uint8)

    def release(self):
        pass


def reader(frames: int, shot: Shot) -> VideoSource:
    v = object.__new__(VideoSource)          # no file, no cv2.VideoCapture
    v.cap = Tape(frames)
    v.src_fps = 30.0
    v.shot = shot
    v.ow, v.oh, v.max_scale = 16, 16, 1.0
    v.cursor = -1
    v.last = None
    return v


def clip(**kw) -> Shot:
    return Shot(src="media/take.mp4", kind="video", duration=2.0, **kw)


def test_running_off_the_end_holds_the_last_frame():
    v = reader(30, clip(tin=0.0, tout=1.5))
    good = v.frame(0.5)
    assert v.frame(2.0) is good          # past the end: the same picture


def test_running_off_the_end_says_nothing_at_all():
    """The bug this file is named for. The frames are simply not there,
    which is normal -- but retrieving after a failed grab makes OpenCV
    print an error that reads, to somebody watching their own film
    render, exactly like a crash."""
    v = reader(30, clip(tin=0.0, tout=1.5))
    v.frame(0.5)
    for t in (1.1, 1.2, 1.3, 2.0):
        v.frame(t)
    assert not v.cap.retrieved_past_end


def test_a_clip_with_no_frames_at_all_is_a_real_error():
    """Holding the last frame needs a last frame. With none, this is not
    a rounding gap -- the file is broken, and saying so beats forty
    seconds of black."""
    import pytest
    v = reader(0, clip(tin=0.0, tout=1.5))
    with pytest.raises(SystemExit):
        v.frame(0.0)


def test_the_frames_that_are_there_are_still_read_in_order():
    v = reader(60, clip(tin=0.0, tout=2.0))
    v.frame(0.0)
    assert v.cursor == 0
    v.frame(1.0)
    assert v.cursor == 30
    assert not v.cap.retrieved_past_end
