"""
booth.py  --  the one window. Paste, record, again, done.

Written for the worst moment it will ever be used in: somebody who is
upset, who has something they need to say now, and who has no attention
left over for a tool. So the whole thing is one window that opens ready
for your words, and closes when you are finished. No folder to find, no
file to make, no second thing to run.

    paste  ->  Ctrl+Enter  ->  talk  ->  SPACE  ->  again, or done

Four screens, one window, in that order. The words you paste are saved
to script.txt on the way past, so nothing you typed is ever lost --
including when you close the window and walk away.

Three worries answered while recording, because a person talking to a
laptop cannot check any of them afterwards:

    am I in shot?           a small self-view
    is it hearing me?       a bar that moves when you speak
    what was I going to say? the script, scrolling

None of that is a second camera. DirectShow hands a webcam to one
program at a time, so a preview that opened the camera itself would
fight the recording. The SAME ffmpeg that writes the file also sends a
small copy of the picture down a pipe and a loudness reading down its
log, and this window draws what arrives. One camera, one process.

No new dependency: tkinter ships with Python and Pillow was already
here. Where tkinter is missing, `available()` says so and recording
falls back to the plain terminal version, unchanged.
"""

from __future__ import annotations

import queue
import re
import subprocess
import threading
import time
from pathlib import Path

# The preview is padded to exactly this, whatever shape the camera is,
# so the reader knows how many bytes make one frame without having to
# ask. 12fps is plenty to see whether your head is in the middle.
PREVIEW_W = 384
PREVIEW_H = 216
PREVIEW_FPS = 12

# ebur128's momentary loudness, in LUFS. Silence in a quiet room sits
# near -70; a person talking at a laptop lands around -30 to -18. These
# are the ends of the bar.
QUIET_LUFS = -55.0
LOUD_LUFS = -12.0

# Below this, after a second or two of trying, nothing is arriving.
SILENT_LUFS = -60.0

WORDS_PER_MINUTE = 105      # deliberately gentle; ↑/↓ change it live
WPM_STEP = 10
WPM_MIN, WPM_MAX = 40, 260

# Where a line break stops looking like a window's doing and starts
# looking like yours. Notepad and mail clients wrap somewhere between 60
# and 80 characters and fill every line to the edge; a phrase you chose
# to put on its own line is almost always shorter than this.
WRAP_WIDTH = 58

TICK_MS = 40
COUNT_FROM = 3

BG = "#0b0b0c"
FG = "#f2f2f0"
DIM = "#8a8a86"
WARN = "#ffa06a"
REC_ON = "#ff4b4b"

_LEVEL = re.compile(rb"M:\s*(-?[\d.]+)")


def available() -> bool:
    try:
        import tkinter                                    # noqa: F401
        from PIL import ImageTk                           # noqa: F401
    except Exception:
        return False
    return True


# --------------------------------------------------------------------------
# The words
# --------------------------------------------------------------------------


def hard_wrapped(lines: list[str]) -> bool:
    """Did a window put these breaks in, or did a person?

    A machine wrapping at a column fills every line it can: each line but
    the last runs right up to the edge. A person breaking a script does
    it at breaths, and those lines come out short and uneven. One short
    line in the middle of a block is therefore a decision, and the whole
    block is left alone.
    """
    if len(lines) < 2:
        return False
    return all(len(ln) >= WRAP_WIDTH for ln in lines[:-1])


def reflow(text: str) -> str:
    """Undo the line breaks a window put in. Keep the ones you typed.

    Text pasted from an email, or typed in Notepad, is hard-wrapped at
    whatever width that window happened to be. Scrolled as-is, those
    breaks land mid-sentence and the eye trips on every one, so they are
    joined back up.

    A script broken by hand is the opposite: those short lines are where
    you meant to breathe, and flattening them is how a prompter makes
    somebody read a list of separate thoughts as one long sentence. They
    are kept exactly as typed. Blank lines are always kept.
    """
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue
        out.append(" ".join(lines) if hard_wrapped(lines) else "\n".join(lines))
    return "\n\n".join(out)


def read_script(project: Path, given: str | None) -> str:
    """Whatever was left here last time, ready to be changed. An explicit
    --script wins; otherwise the project's own script.txt, which is where
    the window saves what you paste."""
    if given:
        p = Path(given)
        if not p.is_absolute():
            p = project / given
        if not p.exists():
            raise SystemExit(f"No script file at {p}")
        return reflow(p.read_text(encoding="utf-8"))
    default = project / "script.txt"
    if default.exists():
        return reflow(default.read_text(encoding="utf-8"))
    return ""


def save_script(path: Path, text: str) -> None:
    """Never lose what somebody typed. Called on every way out of the
    compose screen, including closing the window."""
    text = text.strip()
    if not text:
        return
    try:
        path.write_text(text + "\n", encoding="utf-8")
    except OSError:
        pass


def scroll_speed(text: str, wpm: int, text_px: float) -> float:
    """Pixels per second, derived from how many words there are.

    Set as a reading speed rather than a scroll rate on purpose: the
    same number then means the same thing whether the script is forty
    words or four hundred, and nobody has to translate 'a bit faster'
    into pixels.

    `text_px` is the height of the WORDS -- not of the words plus the
    empty screen they travel across on their way off the top. That
    padding used to be included here, and it is where "105 words a
    minute" quietly became about 170: the words had to cross their own
    height *and* most of a screen in the time it should have taken to
    read them. The lead-out still happens; it just happens at reading
    pace now, like everything else.
    """
    words = max(1, len(text.split()))
    seconds = words / max(1, wpm) * 60.0
    return text_px / seconds


# --------------------------------------------------------------------------
# One capture
# --------------------------------------------------------------------------


class Take:
    """One ffmpeg capture, with its preview and its level pulled off it.

    The pipes MUST be drained even when nobody is looking at them --
    ffmpeg blocks when a pipe fills, and a blocked ffmpeg stops writing
    the file. So the reader threads run until the process ends, whatever
    the window is doing.
    """

    def __init__(self, cmd: list[str], out: Path | None = None):
        self.cmd = cmd
        self.out = out
        self.proc: subprocess.Popen | None = None
        self.frames: queue.Queue = queue.Queue(maxsize=2)
        self.level = -70.0
        self.heard = False
        self.errors: list[str] = []
        self._stop = threading.Event()

    def start(self) -> "Take":
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threading.Thread(target=self._read_frames, daemon=True).start()
        threading.Thread(target=self._read_log, daemon=True).start()
        return self

    def _read_frames(self) -> None:
        size = PREVIEW_W * PREVIEW_H * 3
        out = self.proc.stdout
        while True:
            buf = out.read(size)
            if not buf or len(buf) < size:
                break
            # Newest frame wins. A preview that queues up is a preview
            # that lags behind your own head.
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self.frames.put_nowait(buf)
            except queue.Full:
                pass

    def _read_log(self) -> None:
        for line in iter(self.proc.stderr.readline, b""):
            m = _LEVEL.search(line)
            if m:
                self.level = float(m.group(1))
                if self.level > SILENT_LUFS:
                    self.heard = True
            elif b"rror" in line:
                self.errors.append(line.decode("utf-8", "replace").strip())

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        """`q` on stdin, never a kill: killing ffmpeg leaves an mp4 with
        no index, which is a file that exists, has a size, and opens in
        nothing."""
        if self._stop.is_set():
            return
        self._stop.set()
        try:
            if self.proc and self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def wait(self, timeout: float = 30) -> int:
        if self.proc is None:
            return 1
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        return self.proc.returncode or 0


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------


def session(script: str, script_path: Path, wpm: int, title: str,
            start, finish, seconds: float | None = None) -> None:
    """Open the window and stay in it until the person is finished.

    `start()`         begins one recording and returns the running Take.
    `finish(take)`    is called when that take ends; it returns the lines
                      to show on the review screen.

    Control is inverted -- the window owns the loop, not the caller --
    because the alternative is a window that closes and reopens between
    every take, and something blinking in and out of existence is the
    last thing you want in front of somebody who is already rattled.
    """
    import tkinter as tk
    from PIL import Image, ImageTk

    S = {"stage": "compose", "take": None, "wpm": wpm, "y": 0.0,
         "t0": 0.0, "count": 0, "rolling": False, "script": script, "photo": None}

    root = tk.Tk()
    root.title("film record" + (f" -- {title}" if title else ""))
    root.configure(bg=BG)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{sw}x{int(sh * 0.66)}+0+0")

    def big(parent, text, size, colour=FG, font="Segoe UI", **kw):
        return tk.Label(parent, text=text, bg=BG, fg=colour,
                        font=(font, size), **kw)

    def button(parent, text, command, primary=False):
        return tk.Button(
            parent, text=text, command=command,
            bg="#e8e8e4" if primary else "#26262a",
            fg="#101012" if primary else FG,
            activebackground="#ffffff" if primary else "#34343a",
            activeforeground="#101012" if primary else FG,
            font=("Segoe UI", 15, "bold" if primary else "normal"),
            relief="flat", padx=22, pady=11, cursor="hand2",
            borderwidth=0, highlightthickness=0)

    # ---- screen 1: the words ------------------------------------------
    compose = tk.Frame(root, bg=BG)
    big(compose, "What do you want to say?", 30).pack(anchor="w", pady=(4, 2))
    big(compose, "Paste it here and it will scroll while you talk. "
                 "Or leave it empty and just speak.",
        15, DIM).pack(anchor="w", pady=(0, 14))

    editor = tk.Text(compose, bg="#151518", fg=FG, insertbackground=FG,
                     font=("Georgia", 17), relief="flat", wrap="word",
                     padx=18, pady=16, height=10,
                     selectbackground="#3a3a44", highlightthickness=0)
    editor.pack(fill="both", expand=True)
    if script:
        editor.insert("1.0", script)

    row = tk.Frame(compose, bg=BG)
    row.pack(fill="x", pady=(16, 4))

    # ---- screen 2 and 3: countdown, then recording --------------------
    stage = tk.Frame(root, bg=BG)
    canvas = tk.Canvas(stage, bg=BG, highlightthickness=0)
    canvas.pack(side="top", fill="both", expand=True)

    strip = tk.Frame(stage, bg=BG)
    strip.pack(side="bottom", fill="x", padx=18, pady=(6, 12))

    view = tk.Label(strip, bg="#000000", borderwidth=0,
                    highlightthickness=0)
    view.pack(side="left")
    # A black frame straight away. Without an image, a Label's width and
    # height are counted in CHARACTERS, so the empty preview would open
    # as a black rectangle 384 characters wide.
    blank = ImageTk.PhotoImage(Image.new("RGB", (PREVIEW_W, PREVIEW_H),
                                         (0, 0, 0)))
    view.configure(image=blank)
    view.image = blank

    # The hints are packed BEFORE the gauges. The gauges expand to fill,
    # and whatever is packed after them gets whatever is left -- which,
    # against an expanding sibling, is nothing, and the hints run off
    # the edge of the screen where nobody can read them.
    big(strip, "SPACE  stop this take\n"
               "R  start the words again\n"
               "UP / DOWN  faster, slower",
        13, DIM, justify="right").pack(side="right", anchor="n")

    gauges = tk.Frame(strip, bg=BG)
    gauges.pack(side="left", fill="both", expand=True, padx=22)
    rec_dot = big(gauges, "", 24, REC_ON)
    rec_dot.pack(anchor="w")
    clock = big(gauges, "0:00", 38)
    clock.pack(anchor="w")
    mic = big(gauges, "", 15, DIM, font="Consolas")
    mic.pack(anchor="w", pady=(6, 0))

    # ---- screen 4: what you got ---------------------------------------
    review = tk.Frame(root, bg=BG)
    got = big(review, "", 34)
    got.pack(anchor="w", pady=(30, 6))
    trouble = big(review, "", 16, WARN, justify="left", wraplength=int(sw * .7))
    trouble.pack(anchor="w", pady=(0, 8))
    tally = big(review, "", 15, DIM)
    tally.pack(anchor="w", pady=(0, 22))
    review_row = tk.Frame(review, bg=BG)
    review_row.pack(anchor="w")

    def show(name: str) -> None:
        for f in (compose, stage, review):
            f.pack_forget()
        S["stage"] = name
        # On top only while it matters. During compose you may well be
        # copying the words out of something else, and a window that
        # will not get out of the way is no help at all.
        root.attributes("-topmost", name in ("count", "rec"))
        if name == "compose":
            compose.pack(fill="both", expand=True, padx=44, pady=30)
            editor.focus_set()
        elif name == "review":
            review.pack(fill="both", expand=True, padx=44, pady=20)
        else:
            stage.pack(fill="both", expand=True)

    # ---- the script, scrolling ----------------------------------------
    item = {"id": None}

    def lay_out_words() -> None:
        if item["id"] is not None:
            canvas.delete(item["id"])
            item["id"] = None
        canvas.delete("hint")
        if S["script"]:
            # A narrower column than the screen allows: long lines make
            # the eye track sideways, and sideways is where the camera
            # is not.
            item["id"] = canvas.create_text(
                sw // 2, 0, text=S["script"], fill=FG, font=("Georgia", 34),
                width=int(sw * 0.60), justify="center", anchor="n")
        else:
            canvas.create_text(
                sw // 2, 70, fill=DIM, font=("Segoe UI", 20), anchor="n",
                tags="hint", justify="center",
                text="Just talk.\n\nPress SPACE when you have finished.")
        reset_words()

    def text_height() -> float:
        """How tall the words are. Nothing else -- see scroll_speed."""
        if item["id"] is None:
            return 1.0
        box = canvas.bbox(item["id"])
        return (box[3] - box[1]) if box else 1.0

    def reset_words() -> None:
        S["y"] = canvas.winfo_height() * 0.16
        if item["id"] is not None:
            canvas.coords(item["id"], sw // 2, S["y"])

    # ---- moving between screens ---------------------------------------
    def begin(_=None):
        S["script"] = reflow(editor.get("1.0", "end"))
        save_script(script_path, S["script"])
        lay_out_words()
        S["count"] = COUNT_FROM
        show("count")
        canvas.delete("count")
        tick_count()

    def tick_count():
        canvas.delete("count")
        if S["count"] > 0:
            canvas.create_text(sw // 2, canvas.winfo_height() // 2,
                               text=str(S["count"]), fill=FG,
                               font=("Segoe UI", 150, "bold"), tags="count")
            rec_dot.configure(text="   getting ready", fg=DIM)
            clock.configure(text="")
            mic.configure(text="")
            S["count"] -= 1
            root.after(1000, tick_count)
            return
        canvas.delete("count")
        S["take"] = start()
        S["t0"] = time.time()
        S["rolling"] = False
        show("rec")
        reset_words()
        root.after(TICK_MS, tick_rec)

    def tick_rec():
        take = S["take"]
        if take is None:
            return
        if not take.running:
            end_take()
            return

        got_frame = False
        try:
            buf = take.frames.get_nowait()
            S["photo"] = ImageTk.PhotoImage(
                Image.frombytes("RGB", (PREVIEW_W, PREVIEW_H), buf))
            view.configure(image=S["photo"], width=PREVIEW_W, height=PREVIEW_H)
            got_frame = True
        except queue.Empty:
            pass

        # The clock starts at the first frame, not at the moment ffmpeg
        # was launched. A webcam takes a second or so to wake up, and a
        # clock that counts the waking is a clock that lies -- it would
        # read 0:05 over a take of three and a half seconds. The
        # fixed-length limit is armed from the same instant, so
        # `--seconds 30` means thirty seconds of recording.
        if not S["rolling"] and (got_frame or time.time() - S["t0"] > 3.0):
            S["rolling"] = True
            S["t0"] = time.time()
            if seconds:
                root.after(int(seconds * 1000), take.stop)

        elapsed = time.time() - S["t0"] if S["rolling"] else 0.0
        clock.configure(text=f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}")
        # The dot blinks. A caption that never changes is one you stop
        # believing by the second take.
        rec_dot.configure(text="●  RECORDING" if int(elapsed * 2) % 2
                          else "○  RECORDING", fg=REC_ON)

        filled = int(max(0.0, min(1.0, (take.level - QUIET_LUFS) /
                                  max(1.0, LOUD_LUFS - QUIET_LUFS))) * 24)
        if not take.heard and elapsed > 2.5:
            mic.configure(text="no sound yet -- is the microphone muted?",
                          fg=WARN)
        else:
            mic.configure(text="mic  [" + "#" * filled + "." * (24 - filled) +
                          "]", fg=FG if filled else DIM)

        if item["id"] is not None:
            S["y"] -= scroll_speed(S["script"], S["wpm"], text_height()) * \
                (TICK_MS / 1000.0)
            canvas.coords(item["id"], sw // 2, S["y"])

        root.after(TICK_MS, tick_rec)

    def end_take():
        take, S["take"] = S["take"], None
        if take is None:
            return
        take.stop()
        take.wait()
        lines = finish(take) or []
        # The warnings are written to sit after "Careful:" in the
        # terminal, so they start lower case. On their own line, in a
        # window, they are sentences.
        def upper(s: str) -> str:
            return s[:1].upper() + s[1:]

        got.configure(text=lines[0] if lines else "Got it.")
        trouble.configure(text="\n".join(upper(x) for x in lines[1:-1])
                          if len(lines) > 2 else "")
        tally.configure(text=lines[-1] if len(lines) > 1 else "")
        show("review")

    def again(_=None):
        begin()

    def edit_words(_=None):
        show("compose")

    def done(_=None):
        take = S["take"]
        if take is not None:
            take.stop()
            take.wait()
            S["take"] = None
        save_script(script_path, reflow(editor.get("1.0", "end")))
        root.destroy()

    def stop_take(_=None):
        if S["stage"] == "rec" and S["take"] is not None:
            S["take"].stop()

    # ---- buttons ------------------------------------------------------
    button(row, "Start recording      Ctrl+Enter", begin,
           primary=True).pack(side="left")
    button(row, "Close", done).pack(side="left", padx=10)

    button(review_row, "Record another      Enter", again,
           primary=True).pack(side="left")
    button(review_row, "Change the words", edit_words).pack(side="left",
                                                            padx=10)
    button(review_row, "I am finished      Esc", done).pack(side="left")

    # ---- keys, guarded by which screen you are on ---------------------
    def on_space(e):
        if S["stage"] == "rec":
            stop_take()
            return "break"

    def on_return(e):
        if S["stage"] == "review":
            again()
            return "break"

    def on_escape(e):
        # Never mid-take: Escape while recording would throw away the
        # thing you just said.
        if S["stage"] == "rec":
            stop_take()
        else:
            done()
        return "break"

    def on_key(e):
        if S["stage"] != "rec":
            return
        if e.keysym == "Up":
            S["wpm"] = min(WPM_MAX, S["wpm"] + WPM_STEP)
        elif e.keysym == "Down":
            S["wpm"] = max(WPM_MIN, S["wpm"] - WPM_STEP)
        elif e.keysym in ("r", "R"):
            reset_words()

    root.bind_all("<space>", on_space)
    root.bind_all("<Return>", on_return)
    root.bind_all("<Escape>", on_escape)
    root.bind_all("<Key>", on_key)
    editor.bind("<Control-Return>", lambda e: (begin(), "break")[1])
    root.protocol("WM_DELETE_WINDOW", done)

    show("compose")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        done()
