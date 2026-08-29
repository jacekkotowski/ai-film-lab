"""
record.py  --  talk to your camera, get a file in media/.

The point is to not need OBS for the ordinary case: sit down, say the
thing, stop, and have it already be part of the film. So:

    uv run film record

with no arguments, on a machine this has never run on, has to work. That
means nothing here may assume anything about the hardware. Devices are
discovered at runtime, the capture mode is negotiated from what the
camera says it can do, and the choice is remembered per machine -- not
per project, and never in git, because the next machine has a different
camera and a differently-named microphone.

Recording is the only interactive, long-running command in a toolkit
that is otherwise batch. It is deliberately kept dumb: capture honest
h264+aac into media/ and stop. Everything else -- trimming the silence
at the top, the 1.2x, the tone on the voice -- is a decision recorded in
film.yaml, where you can see it and change it. Nothing is baked into
the file on disk, because media/ is originals and originals are the one
thing you cannot get back.

Windows only for now, via DirectShow. macOS (avfoundation) and Linux
(v4l2) are each about five lines, but untested code that claims to work
is worse than an honest refusal, so they say so instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Recorded takes get this in film.yaml. Not applied to the file on disk:
# the original stays the speed you spoke at, and `speed: 1.2` is a number
# in the edit that you can argue with. Most people, recording themselves
# talking to a lens, are slower than they think.
REC_SPEED = 1.2

# What a recorded file is called. `scaffold` recognises this prefix and
# is the reason a take arrives in film.yaml already sped up.
REC_PREFIX = "rec_"

# Ceiling on the negotiated capture mode. 1080p of a talking head is
# already more than a Short will ever show, and every extra pixel is
# another thing for a laptop to drop frames over.
MAX_CAPTURE_WIDTH = 1920
MIN_CAPTURE_FPS = 24

# DirectShow hands frames over a small ring buffer, and when it fills,
# the frames are simply gone -- "real-time buffer too full" and a stutter
# you only find later. Memory is cheaper than a retake.
RTBUFSIZE = "512M"


def is_recording(stem: str) -> bool:
    """Was this file made by `film record`?"""
    return stem.lower().startswith(REC_PREFIX)


def take_name(when: datetime | None = None) -> str:
    """Sorts chronologically as plain text, which is what `scaffold`
    orders on when there are no numbered filenames."""
    when = when or datetime.now()
    return f"{REC_PREFIX}{when:%Y%m%d-%H%M%S}.mp4"


def next_take_path(media: Path) -> Path:
    """Where the next take goes. Never over the top of an earlier one.

    Takes are named to the second, and two of them cannot normally land
    in the same second. `normally` is doing a lot of work in that
    sentence, and the cost of being wrong is somebody's first take.
    """
    base = take_name()
    path = media / base
    n = 2
    while path.exists():
        path = media / f"{base[:-4]}_{n}.mp4"
        n += 1
    return path


# --------------------------------------------------------------------------
# What is plugged in
# --------------------------------------------------------------------------


@dataclass
class Device:
    name: str
    kind: str          # "video" | "audio" | "none"

    @property
    def usable(self) -> bool:
        """A device reported as `(none)` is registered but not currently
        offering anything -- OBS's virtual camera with OBS shut, most
        often. Listing it is honest; defaulting to it is not."""
        return self.kind in ("video", "audio")


_QUOTED = re.compile(r'"([^"]+)"\s*\((video|audio|none)\)')
_BARE = re.compile(r'"([^"]+)"')


def parse_devices(text: str) -> list[Device]:
    """Read `ffmpeg -list_devices true -f dshow -i dummy`.

    Two output formats in the wild, and a machine you sit down at may
    have either:

      newer   [in#0 @ ..] "EasyCamera" (video)
      older   [dshow @ ..] DirectShow video devices
              [dshow @ ..]  "Integrated Camera"

    The newer form tags every device inline. The older one only has
    section headings, so the kind has to be carried down the list. Try
    inline first; fall back to headings only if nothing was tagged.
    """
    devices: list[Device] = []
    for line in text.splitlines():
        if "Alternative name" in line:
            continue
        m = _QUOTED.search(line)
        if m:
            devices.append(Device(name=m.group(1), kind=m.group(2)))
    if devices:
        return devices

    section = None
    for line in text.splitlines():
        low = line.lower()
        if "directshow video devices" in low:
            section = "video"
            continue
        if "directshow audio devices" in low:
            section = "audio"
            continue
        if "Alternative name" in line or section is None:
            continue
        m = _BARE.search(line)
        if m:
            devices.append(Device(name=m.group(1), kind=section))
    return devices


def _ffmpeg_text(args: list[str]) -> str:
    """Run ffmpeg and read what it said, as UTF-8.

    Not text=True. That decodes using the machine's locale codepage,
    and ffmpeg writes UTF-8 -- so on a Polish Windows the microphone
    called `Zestaw mikrofonow (Realtek High Definition Audio)` comes
    back with its `o` mangled. That matters more than it looks: the
    name is not just printed, it is handed straight back to ffmpeg to
    open the device, and a mangled name opens nothing. The failure is
    silent on an English machine and total on any other.
    """
    from .render import ffmpeg_bin
    r = subprocess.run([ffmpeg_bin()] + args, capture_output=True)
    raw = (r.stderr or b"") + (r.stdout or b"")
    return raw.decode("utf-8", errors="replace")


def list_devices() -> list[Device]:
    # Listing devices is done by failing to open one, so a non-zero exit
    # and a shouty last line are the expected, successful outcome.
    return parse_devices(_ffmpeg_text(
        ["-hide_banner", "-list_devices", "true", "-f", "dshow",
         "-i", "dummy"]))


_MODE = re.compile(r"s=(\d+)x(\d+)\s+fps=([\d.]+)")


def parse_modes(text: str) -> list[tuple[int, int, float]]:
    """Read `ffmpeg -f dshow -list_options true -i video=NAME`."""
    seen: list[tuple[int, int, float]] = []
    for m in _MODE.finditer(text):
        mode = (int(m.group(1)), int(m.group(2)), float(m.group(3)))
        if mode not in seen:
            seen.append(mode)
    return seen


def best_mode(modes: list[tuple[int, int, float]]
              ) -> tuple[int, int, float] | None:
    """The biggest picture that still moves properly.

    Frame rate first, always: a 1080p slideshow at 10fps is worse than
    smooth 720p for the only thing this records, which is a person
    talking. Returns None when there is nothing sensible to say, and
    then the camera is left on its own default -- which is usually
    right, and is certainly better than a guess that fails to open.
    """
    ok = [m for m in modes
          if m[2] >= MIN_CAPTURE_FPS and m[0] <= MAX_CAPTURE_WIDTH]
    if not ok:
        return None
    return max(ok, key=lambda m: (m[0] * m[1], m[2]))


def camera_modes(name: str) -> list[tuple[int, int, float]]:
    return parse_modes(_ffmpeg_text(
        ["-hide_banner", "-f", "dshow", "-list_options", "true",
         "-i", f"video={escape_device(name)}"]))


# --------------------------------------------------------------------------
# Building the command
# --------------------------------------------------------------------------


def escape_device(name: str) -> str:
    """dshow splits `video=X:audio=Y` on the colon and unescapes
    backslashes, so a device whose name contains either has to say so.

    Measured, not assumed: passing the `Alternative name` form from
    -list_devices verbatim fails, because ffmpeg collapses its `\\\\?\\`
    prefix to `\\?\\` and then cannot find the device. Friendly names go
    through intact -- including non-ASCII ones, which is the case that
    matters, since a Polish Windows calls the microphone `Zestaw
    mikrofonow (Realtek High Definition Audio)`.
    """
    return name.replace("\\", "\\\\").replace(":", "\\:")


def input_spec(video: str | None, audio: str | None) -> str:
    parts = []
    if video:
        parts.append(f"video={escape_device(video)}")
    if audio:
        parts.append(f"audio={escape_device(audio)}")
    return ":".join(parts)


def record_command(out: Path, video: str | None, audio: str | None,
                   mode: tuple[int, int, float] | None = None,
                   seconds: float | None = None,
                   ffmpeg: str = "ffmpeg", window: bool = False) -> list[str]:
    """The whole capture, as a list. Pure, so the flags can be checked
    in a test rather than by watching a webcam light.

    With `window`, the same capture also feeds the recording window: a
    small copy of the picture down stdout, and a loudness reading in the
    log. Three outputs, one camera -- DirectShow will not hand the same
    webcam to a second program, so a preview that opened it itself would
    fight the recording rather than show it.
    """
    if not video and not audio:
        raise ValueError("recording needs a camera or a microphone")

    # Quiet on purpose. ffmpeg's live stats are a wall of numbers scrolling
    # past a person who is trying to talk to a lens, and the one number
    # that matters -- did we actually get the frames -- is checked properly
    # afterwards by `verify_take`, where it can be read calmly.
    #
    # The window is the exception: its level meter reads ebur128 out of
    # ffmpeg's own log, and at `error` there is no log to read.
    quiet = "info" if (window and audio) else "error"
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", quiet, "-nostats"]
    cmd += ["-f", "dshow", "-rtbufsize", RTBUFSIZE]
    if mode and video:
        w, h, fps = mode
        cmd += ["-video_size", f"{w}x{h}", "-framerate", f"{fps:g}"]
    # A fixed-length take, when there is no window, is ffmpeg's own job:
    # an INPUT limit, so it stops reading the camera and every output
    # ends together.
    #
    # With the window it cannot be. Measured: `-t` before `-i` ends the
    # capture cleanly with one output, and does NOT end it once the
    # preview and metering outputs are attached -- ffmpeg sits there
    # indefinitely. So the window enforces the limit itself, by sending
    # the same `q` a person's SPACE would send. Which also means the
    # shutdown path is identical either way, and only one of them has to
    # be right.
    if seconds and not window:
        cmd += ["-t", f"{seconds:g}"]
    cmd += ["-i", input_spec(video, audio)]

    if window and video:
        from .booth import PREVIEW_FPS, PREVIEW_H, PREVIEW_W
        # ONE decode, split once into two branches.
        #
        # The obvious way -- naming `-map 0:v` in both the file output
        # and the preview output -- measurably starves the recording.
        # Measured on this machine: 7.5 seconds in front of the camera
        # produced a 1.8 second file, while the same 7.5 seconds with
        # `split` produced 7.2. The preview is a convenience; quietly
        # eating three quarters of what somebody said to pay for it is
        # not a trade anybody would agree to.
        cmd += ["-filter_complex",
                f"[0:v]split=2[main][pv];"
                f"[pv]fps={PREVIEW_FPS},"
                f"scale={PREVIEW_W}:{PREVIEW_H}"
                f":force_original_aspect_ratio=decrease,"
                f"pad={PREVIEW_W}:{PREVIEW_H}:(ow-iw)/2:(oh-ih)/2,"
                f"format=rgb24[pw]",
                "-map", "[main]"]
        if audio:
            cmd += ["-map", "0:a"]
    elif window and audio:
        cmd += ["-map", "0:a"]

    if video:
        # veryfast, not ultrafast: this is running live against a camera,
        # and the difference in CPU is small next to the difference in
        # what the file looks like after the render re-encodes it.
        # yuv420p because webcams hand over yuvj and nothing else plays
        # that reliably.
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-vn"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        cmd += ["-an"]
    cmd.append(str(out))

    if window:
        if video:
            # Padded to an exact size whatever shape the camera is, so
            # the window knows how many bytes make one frame without
            # having to ask the camera anything.
            cmd += ["-map", "[pw]", "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "pipe:1"]
        if audio:
            # Costs nothing measurable, unlike the preview: the file
            # comes out the same length with the meter attached.
            cmd += ["-map", "0:a", "-af", "ebur128=peak=none",
                    "-f", "null", "-"]
    return cmd


# --------------------------------------------------------------------------
# Remembering the choice, per machine
# --------------------------------------------------------------------------


def config_path() -> Path:
    from .cli import toolkit_root
    return toolkit_root() / ".devices.json"


def load_choice() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def save_choice(video: str | None, audio: str | None) -> None:
    config_path().write_text(
        json.dumps({"video": video, "audio": audio}, indent=2,
                   ensure_ascii=False),
        encoding="utf-8")


def choose_devices(devices: list[Device], saved: dict,
                   want_video: str | None = None,
                   want_audio: str | None = None,
                   ) -> tuple[str | None, str | None, list[str]]:
    """Which camera and which microphone, and what to say about it.

    Order: what you asked for on the command line, then what this
    machine chose last time, then the first thing that works. A
    remembered device that is no longer plugged in is not an error --
    it is a different desk. Say so once and carry on with what is here.
    """
    notes: list[str] = []
    cams = [d.name for d in devices if d.kind == "video"]
    mics = [d.name for d in devices if d.kind == "audio"]

    def pick(want, remembered, available, label):
        if want:
            if want in available:
                return want
            raise SystemExit(
                f"No {label} called {want!r} on this machine.\n"
                f"Available: {', '.join(available) or '(none)'}\n"
                f"Run:  uv run film devices")
        if remembered:
            if remembered in available:
                return remembered
            notes.append(
                f"The {label} you used last time is not on this computer, "
                f"so I am using the one that is.")
        return available[0] if available else None

    video = pick(want_video, saved.get("video"), cams, "camera")
    audio = pick(want_audio, saved.get("audio"), mics, "microphone")
    if video and len(cams) > 1 and not want_video and not saved.get("video"):
        notes.append(f"You have {len(cams)} cameras. Using this one. "
                     f"`uv run film devices` shows the others.")
    if audio and len(mics) > 1 and not want_audio and not saved.get("audio"):
        notes.append(f"You have {len(mics)} microphones. Using this one. "
                     f"`uv run film devices` shows the others.")
    return video, audio, notes


# --------------------------------------------------------------------------
# Doing it
# --------------------------------------------------------------------------


def was_silent(path: Path) -> bool:
    """Did the microphone actually pick anything up?

    Only needed when there was no window open to show it live. A mic
    muted in the Windows mixer records a perfect, confident, silent
    take, and the moment to find that out is now.
    """
    text = _ffmpeg_text(["-hide_banner", "-i", str(path), "-map", "0:a",
                         "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", text)
    return bool(m) and float(m.group(1)) < -50.0


def verify_take(path: Path, mode: tuple[int, int, float] | None,
                want_audio: bool,
                heard: bool | None = None) -> tuple[float, list[str]]:
    """Look at what we actually got, and say so before you walk away.

    Dropped frames and a microphone that was muted at the mixer both
    produce a file that exists, has a plausible size, and is wrong. The
    time to find that out is now, while the light is the same and you
    can simply say it again -- not tomorrow, in the edit.
    """
    from .render import ffprobe_bin
    r = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-of", "json",
         "-show_entries", "format=duration:stream=codec_type,nb_frames",
         str(path)],
        capture_output=True, text=True, errors="replace")
    try:
        data = json.loads(r.stdout or "{}")
    except ValueError:
        return 0.0, ["could not read the file back -- check it plays"]

    streams = data.get("streams", [])
    duration = float(data.get("format", {}).get("duration") or 0.0)
    warnings: list[str] = []

    if want_audio and not any(s.get("codec_type") == "audio" for s in streams):
        warnings.append("there is no sound at all in that take -- check the "
                        "microphone is not muted in Windows")
    elif want_audio and (heard is False
                         or (heard is None and was_silent(path))):
        warnings.append("that take is silent. The microphone is connected "
                        "but nothing reached it -- it is probably muted, "
                        "either in Windows or by a switch on the device.")

    frames = next((int(s.get("nb_frames") or 0) for s in streams
                   if s.get("codec_type") == "video"), 0)
    # Not on a very short take. A webcam takes about a second to wake up
    # and hand over its first frames, which on a three-second take looks
    # exactly like a machine that cannot keep up -- and telling somebody
    # their laptop is too slow when it is not is worse than saying
    # nothing.
    if mode and frames and duration > 4.0:
        got = frames / duration
        warnings += rate_note(got, mode[2])
    return duration, warnings


def rate_note(got: float, asked: float) -> list[str]:
    """Why a take came out slower than the rate that was asked for.

    A webcam short of light does not slow down smoothly. It steps down an
    exposure ladder, halving or thirding its rate to hold the shutter
    open twice or three times as long, and reports the full rate the
    whole time. So a take landing on almost exactly half is the camera
    choosing light over motion -- and a measurement, not a guess: the
    same camera on the same laptop gave 2299 frames over 76.9s at a mean
    brightness of 108, and 92 frames over 6.3s at a brightness of 52.
    Both halved together.

    Saying "your machine could not keep up" there is worse than saying
    nothing. It sends somebody off to close programs and check their
    processor when the answer is a lamp.
    """
    if got >= asked * 0.8:
        return []
    ratio = got / max(asked, 0.01)
    if any(abs(ratio - 1.0 / k) < 0.08 for k in (2, 3, 4)):
        return [f"the camera recorded {got:.0f}fps instead of {asked:g}. "
                f"That is what a webcam does when there is not much light "
                f"-- it holds the shutter open longer and gives you half "
                f"the frames. More light on your face fixes it. Nothing "
                f"is wrong with the computer."]
    return [f"got {got:.0f}fps of the {asked:g} asked for -- the machine "
            f"could not keep up. Close what else is running, or record "
            f"smaller."]


def require_windows() -> None:
    if sys.platform != "win32":
        raise SystemExit(
            f"`film record` is Windows-only for now (this is "
            f"{sys.platform}).\n"
            f"Everything else in the toolkit is cross-platform -- record "
            f"with whatever your machine has, drop the file in media/, "
            f"and carry on from `film ingest`.")


def run_recording(cmd: list[str], seconds: float | None) -> int:
    """Run ffmpeg against the camera and stop it cleanly.

    ffmpeg stops on `q` on stdin, and stopping it that way is the whole
    game: killing it leaves an mp4 with no moov atom, which is a file
    that exists, has a size, and will not open in anything. Ctrl-C gets
    the same treatment for the same reason.
    """
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def stop():
        try:
            if p.stdin and not p.stdin.closed:
                p.stdin.write(b"q")
                p.stdin.flush()
        except (OSError, ValueError):
            pass

    try:
        if seconds:
            p.wait(timeout=seconds + 30)
        else:
            try:
                input()
            except EOFError:
                # No console to press ENTER at -- a hook, a script, the
                # bench. Recording until told otherwise is the wrong
                # default there, so stop rather than run forever.
                pass
            stop()
            p.wait(timeout=30)
    except KeyboardInterrupt:
        print("\n  stopping cleanly, one moment...")
        stop()
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
    except subprocess.TimeoutExpired:
        stop()
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
    return p.returncode or 0
