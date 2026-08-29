"""
audio.py  --  build the film's soundtrack.

Three things can make sound, and all three need to end up in the file:

  1. Speech recorded IN your video clips. This is the one that was
     being silently thrown away before -- you talk to camera, and the
     old code muxed only a global track, so your voice vanished.
     Each video shot's audio is cut to its in/out segment and placed
     at that shot's position on the finished timeline.

  2. A narration track (`audio:`), if you recorded one separately.

  3. A music bed (`music:`, or just drop a file in the project's
     music/ folder). Trimmed -- or looped -- to the film's exact
     length, faded in and out, and held at `music_volume` (0.4 by
     default) so it sits under the talking instead of fighting it.

Built as a second pass with one ffmpeg call after the video is
rendered. That is deliberate: the video's true length is known by
then, so the music can be cut to it exactly, and nothing gets
truncated by `-shortest` guessing wrong.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .spec import Film, Shot

CLICK_FADE = 0.02      # seconds of fade at each end of a speech segment

# ffmpeg's speech normaliser: follow the peaks of the voice and expand it
# up towards a target. p=0.7 leaves headroom for the music underneath;
# e=25 is enough expansion to rescue a voice recorded across a windy
# beach; r keeps the rise gentle enough not to breathe.
SPEECH_NORM = "speechnorm=p=0.7:e=25:r=0.0003:l=1"

# The voice, before anything is mixed under it. Both of these ride along
# with `speech_lift`, so `speech_lift: false` in film.yaml still means
# "leave my voice exactly as I recorded it".
#
# Nothing human lives below 80Hz in a spoken recording. What is down
# there is desk thump, traffic, the laptop fan and the microphone's own
# handling noise -- removing it is free headroom, and is inaudible
# except as the absence of mud.
VOICE_FLOOR_HZ = 80

# A gentle shelf around the chest register. This is what "deeper"
# actually is: EQ, not pitch. Pitch-shifting (asetrate) does make you
# sound lower, and it also makes you sound like somebody else -- which
# is the version people regret four minutes into a finished film.
# Keep this small. +2.5dB is warmth; +8dB is a cartoon voice.
VOICE_WARMTH_HZ = 110
VOICE_WARMTH_DB = 2.5


def voice_tone() -> list[str]:
    """The two filters that make a spoken take sound recorded rather
    than captured. Ordered floor-first so the shelf is not lifting
    rumble that is about to be thrown away anyway."""
    return [
        f"highpass=f={VOICE_FLOOR_HZ}",
        f"equalizer=f={VOICE_WARMTH_HZ}:width_type=q:w=0.7:"
        f"g={VOICE_WARMTH_DB}",
    ]


def atempo_chain(speed: float) -> list[str]:
    """Play a take faster without raising its pitch.

    This is the half of `speed:` that was missing. The picture has always
    honoured it; the sound did not, so a shot at speed 1.2 put 1.2
    seconds of voice into a 1.0 second slot -- it ran long, drifted out
    of sync, and every shot after it inherited the error.

    Old ffmpeg builds accept only 0.5..2.0 per atempo, so anything
    outside that range is split across several. 1.2 is a single filter;
    the loop is for the day somebody writes speed: 3.
    """
    out: list[str] = []
    s = float(speed)
    while s > 2.0:
        out.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        out.append("atempo=0.5")
        s /= 0.5
    out.append(f"atempo={s:.6f}")
    return out


def _glob_escape(s: str) -> str:
    """Filenames off a camera contain [ ] often enough to matter, and glob
    reads those as character classes."""
    return s.replace("[", "[[]").replace("]", "[]]")


def _dur(path: Path) -> float:
    from .render import ffmpeg_bin, ffprobe_bin
    exe = ffprobe_bin()
    r = subprocess.run(
        [exe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _has_audio(path: Path) -> bool:
    from .render import ffmpeg_bin, ffprobe_bin
    exe = ffprobe_bin()
    r = subprocess.run(
        [exe, "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return bool(r.stdout.strip())


def speech_chain(start: float, end: float | None, delay: int,
                 speed: float, lift: bool) -> list[str]:
    """The filters one spoken source passes through, in order.

    Pure on purpose: no ffmpeg, no files, no Film. Every number in the
    soundtrack that can be silently wrong is decided here, so it can be
    checked in a test instead of by listening to a finished render and
    wondering whether it is your imagination.

    Order matters and is not arbitrary:
      trim   cut the take down to this shot's window
      tempo  before the normaliser, so the normaliser's rise and fall
             are measured against the timeline you will actually hear
      tone   floor and warmth, then the level lift
      fades  measured on the POST-tempo length
      delay  put it where it belongs on the finished timeline
    """
    chain: list[str] = []
    if end is None:
        if start:
            chain.append(f"atrim=start={start:.3f}")
    else:
        chain.append(f"atrim=start={start:.3f}:end={end:.3f}")
    chain += ["asetpts=PTS-STARTPTS", "aresample=44100"]

    if abs(speed - 1.0) > 1e-3:
        chain += atempo_chain(speed)

    if lift:
        # A voice recorded at arm's length on a phone sits about 30dB
        # below a mastered music track. Bring it up to a normal speaking
        # level FIRST, so everything after this -- the ducking, the music
        # level, the loudness -- is set against a voice that is there.
        chain += voice_tone()
        chain.append(SPEECH_NORM)

    # A few milliseconds at each end. Cutting a pause out of a take
    # splices two waveforms together mid-air, and without this the join
    # is an audible tick.
    #
    # Measured on the SPED-UP length: atempo has already run, so the
    # segment is now (end - start) / speed seconds long. Fading out at
    # the raw figure would schedule the fade past the end of the stream,
    # which is to say: not at all.
    if end is not None:
        seg = (end - start) / speed
        if seg > 0.2:
            chain.append(f"afade=t=in:st=0:d={CLICK_FADE}")
            chain.append(f"afade=t=out:st={seg - CLICK_FADE:.3f}:"
                        f"d={CLICK_FADE}")

    if delay:
        chain.append(f"adelay={delay}|{delay}")
    return chain


def build_soundtrack(film: Film, silent_video: Path, out: Path,
                     quiet: bool = False) -> Path:
    """Mux speech + narration + music onto an already-rendered video."""
    from .render import ffmpeg_bin, ffprobe_bin

    total = film.duration
    inputs: list[str] = ["-i", str(silent_video)]
    filters: list[str] = []
    idx = 1                      # input 0 is the silent video

    # ---- 1 & 2. everything anybody said: speech recorded in the clips,
    # at their positions on the finished timeline, plus a separately
    # recorded narration track if there is one.
    #
    # Collected as plain descriptions first, because the ducking below
    # needs to build this same set of streams a second time.
    # (src, start, end or None for "to the end", delay in ms, speed)
    specs: list[tuple[Path, float, float | None, int, float]] = []

    if film.keep_clip_audio:
        t = 0.0
        for shot in film.shots:
            if shot.kind != "video":
                t += shot.duration
                continue
            src = film.resolve(shot.src)
            # peek/draft swap in a 480p proxy, and proxies are built with
            # -an to keep them small -- so always go back to the ORIGINAL
            # file for sound, whatever the picture is coming from.
            if "analysis" in src.parts and "proxies" in src.parts:
                # Match on the STEM, not the filename. Every proxy is a
                # .mp4 whatever the original was, so looking for
                # media/<name>.mp4 finds nothing when you shot .mkv or
                # .mov -- and the speech then vanishes from peek and draft
                # without a word, while final (which uses the originals)
                # still has it. A silent draft of a talking film.
                found = next((p for p in (film.root / "media").glob(
                    _glob_escape(src.stem) + ".*")
                    if p.suffix.lower() in Shot.VIDEO_EXT), None)
                if found is not None:
                    src = found
            if not src.exists() or not _has_audio(src):
                t += shot.duration
                continue
            specs.append((src, shot.tin, shot.tin + shot.duration * shot.speed,
                          int(round(t * 1000)), shot.speed))
            t += shot.duration

    if film.audio:
        nar = film.resolve(film.audio)
        if nar.exists():
            specs.append((nar, film.audio_offset, None, 0, 1.0))

    def emit(prefix: str) -> list[str]:
        """Add one input and one filter chain per speech source."""
        nonlocal idx
        labels = []
        for i, (src, start, end, delay, speed) in enumerate(specs):
            chain = speech_chain(start, end, delay, speed, film.speech_lift)
            lbl = f"{prefix}{i}"
            filters.append(f"[{idx}:a]" + ",".join(chain) + f"[{lbl}]")
            inputs.extend(["-i", str(src)])
            idx += 1
            labels.append(lbl)
        return labels

    speech_labels = emit("sp")
    key_labels = emit("key") if (film.music and film.music_duck > 0
                                 and specs) else []

    # ---- 3. the music bed ----
    music_label = None
    if film.music:
        mus = film.resolve(film.music)
        if mus.exists():
            mdur = _dur(mus)
            fade = max(0.0, min(film.music_fade, total / 3.0))
            fade_start = max(0.0, total - fade)
            # Loop only if the track is shorter than the film -- looping
            # a long track would be pointless work.
            loop = ["-stream_loop", "-1"] if 0 < mdur < total else []
            inputs += loop + ["-i", str(mus)]
            filters.append(
                f"[{idx}:a]atrim=start=0:end={total:.3f},"
                f"asetpts=PTS-STARTPTS,"
                f"aresample=44100,"
                f"volume={film.music_volume:.3f},"
                f"afade=t=in:st=0:d={fade:.2f},"
                f"afade=t=out:st={fade_start:.2f}:d={fade:.2f}[mus]"
            )
            music_label = "mus"
            idx += 1

    # ---- nothing to do? just copy the video through ----
    if not speech_labels and music_label is None:
        if silent_video.resolve() != out.resolve():
            out.write_bytes(silent_video.read_bytes())
        return out

    # ---- mix ----
    # First, everything anybody said, on one stream.
    speech = None
    if len(speech_labels) == 1:
        speech = speech_labels[0]
    elif speech_labels:
        # normalize=0 keeps each source at the level we set rather than
        # quietly dividing everything by the number of inputs.
        filters.append("".join(f"[{l}]" for l in speech_labels) +
                      f"amix=inputs={len(speech_labels)}:normalize=0:"
                      f"dropout_transition=0[speech]")
        speech = "speech"

    if music_label and speech and film.music_duck > 0 and key_labels:
        # Ducking. The music watches the speech and gets out of its way,
        # then comes back up in the gaps. A fixed music_volume cannot do
        # both jobs: quiet enough to talk over is too quiet to carry the
        # film when nobody is talking.
        #
        # The compressor needs the speech twice -- once as the thing you
        # hear, once as the trigger it listens to. The obvious way to get
        # that is asplit, and the obvious way is wrong: splitting one
        # stream between a mixer and a sidechain deadlocks ffmpeg every so
        # often, and an intermittent hang with no message is the worst
        # failure this tool could have. So the trigger is built from its
        # own decode of the same files. It costs a second pass over some
        # short audio and it cannot deadlock.
        if len(key_labels) == 1:
            key = key_labels[0]
        else:
            filters.append("".join(f"[{l}]" for l in key_labels) +
                          f"amix=inputs={len(key_labels)}:normalize=0:"
                          f"dropout_transition=0[sp_key]")
            key = "sp_key"

        # A compressor reduces by (level_above_threshold) * (1 - 1/ratio),
        # so the ratio saturates fast: 14 buys barely more than 6 and just
        # makes the music vanish. At the 0.45 default this lands around
        # 12-14dB under speech, which is about where broadcast sits -- the
        # music stays present, it just stops competing.
        ratio = 1.0 + 9.0 * film.music_duck
        filters.append(f"[{music_label}][{key}]sidechaincompress="
                      f"threshold=0.02:ratio={ratio:.1f}:attack=5:"
                      f"release=350:makeup=1[ducked]")
        # Music FIRST. amix anchors its output to its first input, and the
        # speech streams are `adelay`-ed to start partway in -- putting a
        # delayed stream first makes the whole mix start late, silencing
        # the music bed underneath the opening shots.
        filters.append(f"[ducked][{speech}]amix=inputs=2:normalize=0:"
                      "dropout_transition=0[mixed]")
        final = "mixed"
    else:
        mix_in = ([music_label] if music_label else []) + \
                 ([speech] if speech else [])
        if len(mix_in) == 1:
            final = mix_in[0]
        else:
            filters.append("".join(f"[{l}]" for l in mix_in) +
                          f"amix=inputs={len(mix_in)}:normalize=0:"
                          f"dropout_transition=0[mixed]")
            final = "mixed"

    # Pad/cut to exactly the film's length, then normalise the loudness.
    #
    # Without this last step a film lands wherever your phone's microphone
    # happened to land, which is usually several dB under everything else
    # in the feed -- and quiet reads as amateur before a word is heard.
    # -14 LUFS is what YouTube, Spotify and the rest normalise to, so
    # hitting it means nobody's player has to touch your mix.
    norm = (f"loudnorm=I={film.loudness:.1f}:TP=-1.5:LRA=11,aresample=44100,"
            if film.loudness else "")
    filters.append(f"[{final}]apad,atrim=0:{total:.3f},"
                  f"{norm}alimiter=limit=0.95[aout]")

    args = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error"]
    args += inputs
    args += ["-filter_complex", ";".join(filters),
             "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(out)]

    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed building the soundtrack:\n"
                         + r.stderr.strip()[-700:])
    if not quiet:
        bits = []
        if speech_labels:
            bits.append(f"{len(speech_labels)} speech source(s)")
        if music_label:
            if speech_labels and film.music_duck > 0:
                bits.append(f"music at {int(film.music_volume * 100)}% where "
                            f"nobody is talking, ducked under where they are")
            else:
                bits.append(f"music at {int(film.music_volume * 100)}%")
        print(f"  sound: {', '.join(bits)}")
    return out
