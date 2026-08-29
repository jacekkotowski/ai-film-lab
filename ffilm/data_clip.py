"""
data_clip.py  --  turn a table into a short animated clip.

    uv run film data-clip bars.csv -p my_movie --kind bar_race --out data/bars.mp4

The output is a plain mp4, sized and timed to match your film. Once it
exists, reference it in film.yaml exactly like any photo or video clip:

    - src: data/bars.mp4
      duration: 6.0
      move: static

This is deliberately small. It does not try to be a charting library --
matplotlib already is one. What this adds is: animate a plain CSV over
time with one command, at the right size and frame rate for THIS film,
with the same grain/vignette/grade already applied so it doesn't look
like a chart pasted onto a movie.

Kinds:
  line        a line growing left to right over time
  bar_race    horizontal bars reordering as values change over time
  counter     one big number climbing to its final value
  scatter_in  points fading/growing in, for a "the data arrives" beat

CSV shape expected (long format, one row per time step per series):
  time, series, value
  0,    Sales,  120
  1,    Sales,  180
  0,    Costs,  90
  1,    Costs,  95

`time` can be numeric (seconds, years, whatever) or dates -- both are
sorted and spaced proportionally, so real calendar gaps show correctly.
"""

from __future__ import annotations

import csv as csv_mod
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # no display needed -- we only ever save frames
import matplotlib.pyplot as plt
import numpy as np

from .render import ffmpeg_bin
import subprocess


def _read_long_csv(path: Path) -> tuple[list, dict[str, list[float]]]:
    """time, series, value  ->  (sorted unique times, {series: [values]})
    Missing (time, series) pairs are forward-filled from the last known
    value, so a series that stops updating just holds instead of
    vanishing or crashing the plot.
    """
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv_mod.DictReader(fh):
            rows.append((r["time"], r["series"], float(r["value"])))

    times_raw = sorted({r[0] for r in rows}, key=lambda t: _try_num(t))
    series_names = sorted({r[1] for r in rows})

    grid: dict[str, list[float]] = {s: [] for s in series_names}
    last: dict[str, float] = {}
    by_tp = {(t, s): v for t, s, v in rows}
    for t in times_raw:
        for s in series_names:
            if (t, s) in by_tp:
                last[s] = by_tp[(t, s)]
            grid[s].append(last.get(s, 0.0))

    return times_raw, grid


def _try_num(t: str) -> float:
    try:
        return float(t)
    except ValueError:
        # crude date fallback: YYYY-MM-DD -> a sortable number
        parts = t.replace("/", "-").split("-")
        try:
            return int(parts[0]) * 400 + int(parts[1]) * 31 + int(parts[2])
        except Exception:
            return 0.0


# --------------------------------------------------------------------------
# Rendering: matplotlib draws each frame to a PNG, ffmpeg assembles the mp4.
# Slower than the main renderer, but data clips are short and made once.
# --------------------------------------------------------------------------


def _style_axes(ax, dark: bool) -> None:
    fg = "#e8e6e2" if dark else "#20211f"
    ax.tick_params(colors=fg, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color(fg)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.label.set_color(fg)
    ax.yaxis.label.set_color(fg)


def render_line(times, grid, out_frames: Path, w: int, h: int, fps: int,
                seconds: float, dark: bool = True) -> int:
    n = max(2, int(seconds * fps))
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")
    _style_axes(ax, dark)

    x = np.linspace(0, 1, len(times))
    colors = plt.cm.tab10(np.linspace(0, 1, len(grid)))
    ymax = max(max(v) for v in grid.values()) * 1.1 or 1.0

    for i in range(n):
        ax.clear()
        ax.set_facecolor("none")
        _style_axes(ax, dark)
        frac = (i + 1) / n
        cutoff = max(1, int(frac * len(times)))
        for (name, vals), c in zip(grid.items(), colors):
            ax.plot(x[:cutoff], vals[:cutoff], color=c, linewidth=3, label=name)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, ymax)
        ax.set_xticks([])
        if len(grid) > 1:
            leg = ax.legend(loc="upper left", frameon=False, fontsize=11)
            for text in leg.get_texts():
                text.set_color("#e8e6e2" if dark else "#20211f")
        fig.savefig(out_frames / f"f{i:05d}.png", transparent=True)
    plt.close(fig)
    return n


def render_bar_race(times, grid, out_frames: Path, w: int, h: int, fps: int,
                    seconds: float, dark: bool = True) -> int:
    n = max(2, int(seconds * fps))
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_alpha(0.0)
    names = list(grid.keys())
    colors = dict(zip(names, plt.cm.tab10(np.linspace(0, 1, len(names)))))
    xmax = max(max(v) for v in grid.values()) * 1.15 or 1.0
    fg = "#e8e6e2" if dark else "#20211f"

    for i in range(n):
        ax.clear()
        ax.set_facecolor("none")
        _style_axes(ax, dark)
        t_idx = min(len(times) - 1, int((i / (n - 1)) * (len(times) - 1)))
        vals = {name: grid[name][t_idx] for name in names}
        order = sorted(vals, key=lambda k: vals[k])
        y = np.arange(len(order))
        widths = [vals[k] for k in order]
        ax.barh(y, widths, color=[colors[k] for k in order], height=0.6)
        for yi, k in zip(y, order):
            ax.text(vals[k] + xmax * 0.015, yi, f"{k}  {vals[k]:,.0f}",
                    va="center", fontsize=12, color=fg)
        ax.set_xlim(0, xmax)
        ax.set_yticks([])
        ax.set_xticks([])
        fig.savefig(out_frames / f"f{i:05d}.png", transparent=True)
    plt.close(fig)
    return n


def render_counter(times, grid, out_frames: Path, w: int, h: int, fps: int,
                   seconds: float, dark: bool = True) -> int:
    """One series, one big number climbing to its final value. Ignores
    every series but the first -- this kind is for a single headline
    figure, not a comparison."""
    n = max(2, int(seconds * fps))
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.axis("off")
    name, vals = next(iter(grid.items()))
    final = vals[-1]
    fg = "#e8e6e2" if dark else "#20211f"

    for i in range(n):
        ax.clear()
        ax.axis("off")
        t = (i / (n - 1)) ** 0.6              # ease-out: fast then settle
        current = final * t
        ax.text(0.5, 0.55, f"{current:,.0f}", ha="center", va="center",
                fontsize=64, color=fg, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.5, 0.30, name, ha="center", va="center",
                fontsize=18, color=fg, alpha=0.8, transform=ax.transAxes)
        fig.savefig(out_frames / f"f{i:05d}.png", transparent=True)
    plt.close(fig)
    return n


RENDERERS = {"line": render_line, "bar_race": render_bar_race,
            "counter": render_counter}


def make_clip(csv_path: Path, out: Path, kind: str = "line",
             width: int = 1920, height: int = 1080, fps: int = 24,
             seconds: float = 6.0, dark: bool = True,
             bg: str = "#141414") -> Path:
    """bg is the background the chart is composited onto. mp4/h264 can't
    carry real transparency, so "transparent" matplotlib frames actually
    get flattened onto white by ffmpeg unless we hand them a real color
    to sit on first -- match this to your film's look (dark footage:
    leave the default; light/paper look: pass a light bg)."""
    if kind not in RENDERERS:
        raise SystemExit(f"Unknown kind {kind!r}. Choose from: "
                         f"{', '.join(RENDERERS)}")
    times, grid = _read_long_csv(csv_path)
    if not grid:
        raise SystemExit(f"{csv_path} has no data rows.")

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        frames_dir = Path(tmp)
        n = RENDERERS[kind](times, grid, frames_dir, width, height, fps,
                            seconds, dark)
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", f"color=c={bg}:s={width}x{height}:r={fps}",
             "-r", str(fps), "-i", str(frames_dir / "f%05d.png"),
             "-filter_complex",
             "[0:v][1:v]overlay=shortest=1:format=auto[v]",
             "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(out)],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"ffmpeg failed assembling the clip: "
                             f"{r.stderr.strip()[-400:]}")
    return out
