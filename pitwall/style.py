"""Pit Wall Notes visual identity. Drivers keep their team colours; purple is the brand accent, and in data it only
marks a fastest sector, as on F1 timing screens."""
import json
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch

BG = "#0a0b0e"
FRAME = "#27272a"
GRID = "#1c1c20"
TEXT = "#f4f4f5"
MUTED = "#a1a1aa"
FAINT = "#52525b"
PURPLE = "#a855f7"
FALLBACK_COLOUR = MUTED.lstrip("#")

MONO = ["JetBrainsMono Nerd Font", "JetBrains Mono", "Menlo", "DejaVu Sans Mono"]
SANS = ["Helvetica Neue", "Arial", "DejaVu Sans"]
# Race charts (positions, pace) use the sans look of the F1 data community, with timing-screen digits.
WORDS = ["Avenir Next", *SANS]
DIGITS = ["DIN Alternate", *WORDS]
TYRES = {"SOFT": "#e8202f", "MEDIUM": "#f5c400", "HARD": "#f2f3f5", "INTERMEDIATE": "#2fb34a", "WET": "#2f6fe0"}
REPO = "github.com/pitwallcoder/f1-telemetry-lab"


# Every chart sets the same matplotlib keys, so none inherits the look of the chart drawn before it.
BASE_RC = {"font.monospace": MONO, "text.color": TEXT, "axes.labelcolor": MUTED, "xtick.color": FAINT,
           "ytick.color": FAINT, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8}


def _canvas(family, sans, size, dpi):
    matplotlib.rcParams.update({**BASE_RC, "font.family": family, "font.sans-serif": sans})
    fig = Figure(figsize=size, dpi=dpi)
    FigureCanvasAgg(fig)  # text_row measures text as it lays it out
    fig.patch.set_facecolor(BG)
    return fig


def figure():
    fig = _canvas("monospace", SANS, (12.8, 7.2), 125)
    fig.patches.append(FancyBboxPatch((0.012, 0.02), 0.976, 0.96, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, fill=False, edgecolor=FRAME, linewidth=1))
    return fig


def race_figure(title):
    """16:9 dark canvas with a centred title and the account byline."""
    fig = _canvas("sans-serif", WORDS, (16, 9), 135)
    fig.text(0.5, 0.95, title, color=TEXT, fontsize=21, fontweight="bold", ha="center")
    fig.text(0.5, 0.915, "by @pitwallcoder", color=PURPLE, fontsize=11.5, fontweight="semibold", ha="center")
    return fig


def story_figure(headline, context, how_to_read):
    """16:9 canvas for readers who are not data people: the event in small caps, the takeaway as the title, then one
    plain sentence on how to read the chart."""
    fig = _canvas("sans-serif", WORDS, (16, 9), 135)
    fig.text(0.05, 0.94, context.upper(), color=MUTED, fontsize=10.5, fontweight="semibold")
    fig.text(0.95, 0.94, "@pitwallcoder", color=PURPLE, fontsize=11, fontweight="semibold", ha="right")
    fig.text(0.05, 0.875, headline, color=TEXT, fontsize=25, fontweight="bold")
    fig.text(0.05, 0.83, how_to_read, color=MUTED, fontsize=12)
    return fig


def surname(driver):
    full = (driver.get("full_name") or "").split()
    return driver.get("last_name") or (full[-1].title() if full else driver.get("name_acronym", "?"))


def tower(fig, rows, top=0.75, bottom=0.1, columns=(0.05, 0.53)):
    """Ranked rows like a timing tower, split over `columns` when long: each row is the driver record and its cells,
    (x offset, text, colour, text kwargs), drawn after the position and a chip in the team colour."""
    per_column = -(-len(rows) // len(columns))
    step = min(0.06, (top - bottom) / max(per_column - 1, 1))
    for i, (driver, cells) in enumerate(rows):
        x, y = columns[i // per_column], top - (i % per_column) * step
        fig.text(x, y, str(i + 1), color=FAINT, fontsize=12, va="center", ha="right", family=DIGITS)
        fig.patches.append(FancyBboxPatch((x + 0.012, y - 0.012), 0.005, 0.024, boxstyle="round,pad=0,rounding_size=0.002",
                                          transform=fig.transFigure, facecolor=team_colour(driver), edgecolor="none"))
        for dx, text, colour, kwargs in cells:
            fig.text(x + 0.027 + dx, y, text, color=colour, va="center", **{"fontsize": 13, **kwargs})


def bare_axes(fig, rect):
    ax = fig.add_axes(rect)
    style_axes(ax)
    ax.grid(False)
    return ax


def team_colour(driver):
    return f"#{driver.get('team_colour') or FALLBACK_COLOUR}"


def context_line(fig, code, context):
    text_row(fig, 0.04, 0.925, [(code.upper(), PURPLE, {"fontsize": 9, "fontweight": "bold"}),
                                (f"· {context}".upper(), MUTED, {"fontsize": 9})], gap=0.006)


def text_row(fig, x, y, parts, gap=0.012):
    """Draw (text, colour, extra text kwargs) pieces left to right on one baseline."""
    renderer = fig.canvas.get_renderer()
    for text, colour, kwargs in parts:
        drawn = fig.text(x, y, text, color=colour, **kwargs)
        x = fig.transFigure.inverted().transform(drawn.get_window_extent(renderer).corners()[-1])[0] + gap


def footer(fig, sources):
    fig.text(0.04, 0.045, "@pitwallcoder", fontsize=9, color=TEXT)
    fig.text(0.96, 0.045, f"{sources} · code: {REPO}", fontsize=8, color=FAINT, ha="right")


def style_axes(ax):
    ax.set_facecolor(BG)
    ax.grid(color=GRID, linewidth=0.8)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)


def highlight(ax, x0, x1, colour, alpha=0.12):
    ax.axvspan(x0, x1, color=colour, alpha=alpha, linewidth=0)


def corner_ticks(ax, corner_d, m_per_char=32, padding_m=12):
    last_d, last_len = -np.inf, 0
    for n, d in corner_d:
        ax.axvline(d, color=GRID, linewidth=0.8, zorder=0)
        label = str(n)
        if d - last_d < (last_len + len(label)) / 2 * m_per_char + padding_m:
            continue
        ax.annotate(label, xy=(d, 1), xycoords=("data", "axes fraction"), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7.5, color=MUTED)
        last_d, last_len = d, len(label)


def rotate(x, y, degrees):
    a = np.radians(degrees)
    return x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)


def outward(x, y, px, py):
    """Unit vector across the track at the point of (x, y) nearest (px, py), on the side away from the middle of the
    circuit: where a label sits clear of the track."""
    i = int(np.argmin((x - px) ** 2 + (y - py) ** 2))
    dx, dy = x[min(i + 1, len(x) - 1)] - x[max(i - 1, 0)], y[min(i + 1, len(y) - 1)] - y[max(i - 1, 0)]
    normal = np.array([-dy, dx]) / max(np.hypot(dx, dy), 1e-9)
    return normal if normal @ np.array([px - np.mean(x), py - np.mean(y)]) >= 0 else -normal


def track_map(fig, rect, x, y, zones, finish, rotation=0):
    """`zones` are (tag, mask over the samples, colour); `finish` is the car position at the line and a moment
    later, which gives the line its direction."""
    ax = fig.add_axes(rect)
    x, y = rotate(np.asarray(x, float), np.asarray(y, float), rotation)
    ax.plot(x, y, color=FAINT, linewidth=2.5, solid_capstyle="round")
    (fx, fy), (nx, ny) = (rotate(px, py, rotation) for px, py in finish)
    dx, dy = nx - fx, ny - fy
    half = 0.035 * max(np.ptp(x), np.ptp(y)) / np.hypot(dx, dy)
    ax.plot([fx - dy * half, fx + dy * half], [fy + dx * half, fy - dx * half],
            color=TEXT, linewidth=2, solid_capstyle="butt", zorder=3)
    for tag, mask, colour in zones:
        ax.plot(x[mask], y[mask], color=colour, linewidth=3.5, solid_capstyle="round")
        mid = np.flatnonzero(mask)[mask.sum() // 2]
        ax.annotate(tag, (x[mid], y[mid]), xytext=(-12, -12), textcoords="offset points",
                    color=colour, fontsize=10, fontweight="bold", ha="center", va="center")
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def lap_time(seconds):
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}:{rest:06.3f}"


def save(fig, facts, code, name, out_dir="out"):
    """The chart PNG and its facts JSON in out/<code>/, named <code>_<name>; returns the PNG path."""
    folder = Path(out_dir) / code.lower()
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / f"{code.lower()}_{name}"
    fig.savefig(f"{stem}.png", facecolor=BG)
    Path(f"{stem}.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False))
    return Path(f"{stem}.png")
