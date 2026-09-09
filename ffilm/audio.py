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
# r keeps the rise gentle enough not to breathe.
#
# e was 25, and 25 is what put a waterfall between the sentences.
# Expansion does not know what speech is -- it lifts whatever is quiet,
# and between two sentences the only quiet thing is the room. Measured on
# a real take, the same one second of room tone, everything else equal:
#
#     raw                                     -45.3 dB
#     through e=25                            -17.5 dB     +27.8
#     the voice on that take                  -15.0 dB
#
# The room was being brought to within 2.5dB of the person talking. e=6
# is still three times ffmpeg's own default, still rescues a voice
# recorded too quietly, and leaves the gaps at -66dB. The voice itself
# measures the same either way -- -16.3dB before and after, so this costs
# nothing where it matters.
SPEECH_NORM = "speechnorm=p=0.7:e=6:r=0.0003:l=1"

# Before the expansion: take the hiss out, so there is less of it to
# lift. Broadband, gentle, and it does not touch the voice.
#
# `nf` tells afftdn where the noise floor is, and it is ABSOLUTE dBFS --
# so a fixed number is only right for a take recorded at the level it was
# tuned for. It used to be -25: the loud end of the filter's own range
# (-80..-20), and 25dB hotter than ffmpeg's own default. On a take
# peaking near 0dBFS that is survivable. On a quiet one it is not.
# Consonants are broadband and low-energy, so to a spectral denoiser
# that has been told the room sits at -25dB, an `s` IS the room.
#
# Measured on two of my own takes -- sibilance (4-10kHz, relative to the
# whole signal) against not denoising at all:
#
#                     take at -17dBFS peak     take at 0dBFS peak
#                     (floor -56, SNR 17)      (floor -38, SNR 23)
#     nf=-25                -9.2 dB                  -1.1 dB
#     nf=-50                -0.5 dB                   0.0 dB
#     nf=-50:tn=1           -0.2 dB                   0.0 dB
#
# That 9.2dB is entirely consonants, and it is why a quiet take can come
# back sounding like the plosives were edited out. They were.
#
# `tn=1` is what makes one setting serve every take: afftdn tracks the
# noise floor as it goes instead of trusting the number. It also adapts
# in the useful direction -- on the quieter take, the one with the WORSE
# signal-to-noise ratio, it removed 11.7dB of hiss; on the cleaner one,
# 2.7dB. `nf` stays at ffmpeg's default as the estimate it starts from.
#
# Not `tr=1` (track residual). It denoises harder -- 11.6dB on the loud
# take -- and starts costing consonants again on the quiet one (-2.8dB).
#
# Caveat worth knowing: tracking needs a little audio to converge, and
# `speech_chain` trims per shot. A shot starting mid-word gives it no
# room tone to learn from, so it does less. Less is the safe direction.
DENOISE = "afftdn=nf=-50:tn=1"

# After the expansion: close the gaps completely. This has to come after,
# not before -- a gate ahead of the normaliser is pointless, because
# whatever leaks through gets expanded anyway, and a gate is the one
# thing here that measured EXACTLY no change when placed first.
NOISE_GATE = "agate=threshold=0.03:ratio=9:attack=10:release=250:knee=4"

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


# Windows will not run a command longer than 32767 characters, and this
# is the one command here that grows without limit: the filter graph
# gains a chain of about 350 characters for every separate piece of
# speech, and every piece is built TWICE -- once for what you hear and
# once for the sidechain that ducks the music under it (see the note in
# build_soundtrack about why the trigger is its own decode).
#
# Nine talking shots, which is one ordinary take cut at its pauses, is
# already eighteen. A ten-minute take is routinely thirty pieces, so
# sixty chains, and past the limit the whole film loses its soundtrack
# for a reason no error message would ever have explained.
#
# Left generous, because the inline form is what has always worked and
# what every version of ffmpeg accepts. The file form below is only for
# the graphs that genuinely will not fit.
COMMAND_LIMIT = 24000

_graph_flag: list = []          # one probe per process, cached


def graph_file_flag() -> str | None:
    """How THIS ffmpeg takes a filter graph from a file, or None.

    It is not one spelling. `-filter_complex_script` was the answer for
    years and was removed in ffmpeg 7.1; the generic `-/filter_complex`
    replaced it and does not exist before that. Measured here: 9.0.1
    rejects the old one outright with "Unrecognized option", which is a
    failure at argument-parsing time, before any work -- so asking is
    cheap and guessing is not.

    Asked with a tenth of a second of silence, once, and remembered.
    """
    if _graph_flag:
        return _graph_flag[0]

    from .render import ffmpeg_bin
    import tempfile

    answer = None
    with tempfile.TemporaryDirectory() as d:
        probe = Path(d) / "g.txt"
        probe.write_text("[0:a]anull[a]", encoding="utf-8")
        for flag in ("-/filter_complex", "-filter_complex_script"):
            try:
                r = subprocess.run(
                    [ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
                     "-f", "lavfi", "-i", "anullsrc=d=0.1",
                     flag, str(probe), "-map", "[a]", "-t", "0.1",
                     "-f", "null", "-"],
                    capture_output=True, text=True, errors="replace",
                    timeout=30)
            except (OSError, subprocess.SubprocessError):
                continue
            if r.returncode == 0:
                answer = flag
                break
    _graph_flag.append(answer)
    return answer


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
        # Order is the whole trick: clean, then lift, then close the
        # gaps. Denoise first so the expander has less hiss to find,
        # gate last so anything it did find is shut off between
        # sentences. All three ride with `speech_lift`, so
        # `speech_lift: false` still means "exactly as I recorded it".
        chain += voice_tone()
        chain.append(DENOISE)
        chain.append(SPEECH_NORM)
        chain.append(NOISE_GATE)

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
                     fps: int | None = None, quiet: bool = False) -> Path:
    """Mux speech + narration + music onto an already-rendered video.

    `fps` is the rate the picture was ACTUALLY rendered at -- peek and
    draft may differ from film.fps -- because every position below is
    measured on the frame grid the picture is already on. Placing sound
    at the exact second instead is what put the lips out of step: see
    spec.frames_for.
    """
    from .render import ffmpeg_bin, ffprobe_bin
    from .spec import frames_for

    fps = fps or film.fps
    # The film's real length is whole frames, not the sum of the numbers
    # in film.yaml -- and the music is cut to it.
    total = sum(frames_for(s.duration, fps) for s in film.shots) / fps
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
        # Counted in FRAMES, not seconds. The picture advances a whole
        # frame at a time, so a soundtrack that advances by film.yaml's
        # decimals parts company with it a little at every cut, and the
        # gap is the running total of every rounding so far.
        at = 0
        for shot in film.shots:
            n = frames_for(shot.duration, fps)
            if shot.kind != "video":
                at += n
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
                at += n
                continue
            # The segment is as long as the PICTURE is, for the same
            # reason: n/fps seconds of screen, times speed, is how much
            # of the take was actually shown.
            specs.append((src, shot.tin,
                          shot.tin + (n / fps) * shot.speed,
                          int(round(at / fps * 1000)), shot.speed))
            at += n

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

    graph = ";".join(filters)
    tail = ["-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(out)]
    head = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error"] + inputs

    written: Path | None = None
    if len(" ".join(head + tail)) + len(graph) < COMMAND_LIMIT:
        args = head + ["-filter_complex", graph] + tail
    else:
        # Too long for a Windows command line -- see COMMAND_LIMIT. Hand
        # ffmpeg the graph in a file instead.
        written = out.with_name(out.stem + "__filters.txt")
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_text(graph.replace(";", ";\n"), encoding="utf-8")
        flag = graph_file_flag()
        if flag is None:
            written.unlink(missing_ok=True)
            raise SystemExit(
                "This film has too many separate pieces of speech in it "
                "for one ffmpeg command, and this ffmpeg is too old to "
                "take the filter graph in a file.\n"
                "Update it:  winget install --id Gyan.FFmpeg -e\n"
                "Or join some shots up in film.yaml -- each `in:`/`out:` "
                "pair on a talking clip is one of the pieces.")
        args = head + [flag, str(written)] + tail

    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           errors="replace")
    finally:
        if written is not None:
            written.unlink(missing_ok=True)
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
